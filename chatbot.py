from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import openai
import requests
from datetime import datetime
import locale
import openpyxl

# Configurações
load_dotenv()

try:
    locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
except:
    locale.setlocale(locale.LC_TIME, "")  # fallback

app = Flask(__name__)

# Chaves de API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
WHATSAPP_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("WHATSAPP_TOKEN")

client_openai = openai.Client(api_key=OPENAI_API_KEY)

WHATSAPP_API_URL = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

# Funções auxiliares
def obter_data_hora():
    agora = datetime.now()
    data = agora.strftime("%d de %B de %Y")
    dias_semana = {
        "Monday": "segunda-feira", "Tuesday": "terça-feira", "Wednesday": "quarta-feira",
        "Thursday": "quinta-feira", "Friday": "sexta-feira", "Saturday": "sábado", "Sunday": "domingo"
    }
    dia_semana = dias_semana.get(agora.strftime("%A"), agora.strftime("%A"))
    return data, dia_semana

def obter_previsao_tempo(cidade, pais):
    if not cidade or not pais:
        return {"erro": "Cidade e país são obrigatórios."}
    url = f"http://api.openweathermap.org/data/2.5/weather?q={cidade},{pais}&appid={OPENWEATHER_API_KEY}&units=metric&lang=pt"
    try:
        r = requests.get(url)
        d = r.json()
        if r.status_code != 200:
            return {"erro": f"Não encontrei previsão para '{cidade}, {pais}'."}
        return {
            "cidade": cidade,
            "descricao": d['weather'][0]['description'],
            "temperatura": d['main']['temp'],
            "sensacao": d['main']['feels_like'],
            "umidade": d['main']['humidity'],
            "vento": d['wind']['speed']
        }
    except Exception as e:
        return {"erro": str(e)}

def obter_previsao_estendida(cidade, pais):
    if not cidade or not pais:
        return {"erro": "Cidade e país são obrigatórios."}
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={cidade},{pais}&cnt=3&appid={OPENWEATHER_API_KEY}&units=metric&lang=pt"
    try:
        r = requests.get(url)
        d = r.json()
        if r.status_code != 200:
            return {"erro": f"Não encontrei previsão para '{cidade}, {pais}'."}
        previsoes = []
        for dia in d["list"]:
            data = datetime.utcfromtimestamp(dia["dt"]).strftime("%d/%m/%Y")
            previsoes.append({
                "data": data,
                "descricao": dia["weather"][0]["description"],
                "min": dia["main"]["temp_min"],
                "max": dia["main"]["temp_max"]
            })
        return {"previsao": previsoes}
    except Exception as e:
        return {"erro": str(e)}

def enviar_mensagem_ia(mensagem, cidade=None, pais=None):
    try:
        if cidade and pais:
            clima = obter_previsao_tempo(cidade, pais)
            cidade_confirmada = f"A cidade que você informou foi {cidade} ({pais})."
            if 'erro' in clima:
                clima_info = "Não consegui obter a previsão do tempo."
            else:
                clima_info = f"🌦️ Clima: {clima['descricao']}, Temperatura: {clima['temperatura']}°C, Sensação: {clima['sensacao']}°C."
        else:
            cidade_confirmada = "Você não informou a cidade nem o país."
            clima_info = "Não foi possível buscar o clima sem a cidade e o país."

        prompt = (
            f"Você é um assistente agrícola no sistema Campo Inteligente.\n"
            f"📍 {cidade_confirmada}\n"
            f"🌦️ {clima_info}\n"
            f"❓ Pergunta: {mensagem}"
        )

        resposta = client_openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.4
        )
        conteudo = resposta.choices[0].message.content.strip() if resposta.choices else "Não consegui gerar uma resposta."
        return {"resposta": conteudo}
    except Exception as e:
        return {"erro": str(e)}

def enviar_mensagem_whatsapp(numero_destino, mensagem):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "text",
        "text": {
            "body": mensagem
        }
    }
    response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
    return response.status_code, response.json()

def salvar_planilha(dados):
    try:
        arquivo = "respostas_agricultores_" + datetime.now().strftime("%Y%m%d%H%M%S") + ".xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Respostas"
        ws.append(["Nome", "Localização", "Data", "Dia da Semana"])
        for linha in dados:
            ws.append(linha)
        wb.save(arquivo)
        return {"arquivo_criado": arquivo}
    except Exception as e:
        return {"erro": str(e)}

# Endpoints
@app.route("/", methods=["GET", "POST"])
def home():
    return {"mensagem": "🚜 API Campo Inteligente Rodando!"}

@app.route("/localizacao", methods=["GET"])
def localizacao():
    return jsonify({"mensagem": "Agora a cidade e país devem ser informados pelo usuário."})

@app.route("/previsao", methods=["GET"])
def previsao():
    cidade = request.args.get("cidade")
    pais = request.args.get("pais")
    return jsonify(obter_previsao_tempo(cidade, pais))

@app.route("/previsao_estendida", methods=["GET"])
def previsao_estendida():
    cidade = request.args.get("cidade")
    pais = request.args.get("pais")
    return jsonify(obter_previsao_estendida(cidade, pais))

@app.route("/perguntar", methods=["POST"])
def perguntar():
    data = request.json
    mensagem = data.get("mensagem")
    cidade = data.get("cidade")
    pais = data.get("pais")
    return jsonify(enviar_mensagem_ia(mensagem, cidade, pais))

@app.route("/salvar_agricultores", methods=["POST"])
def salvar_agricultores():
    dados = request.json.get("dados", [])
    return jsonify(salvar_planilha(dados))

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Erro de verificação", 403

    if request.method == "POST":
        data = request.json
        print("🔔 Webhook recebido:", data)

        try:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']

            # Verifica se tem mensagem
            messages = value.get('messages')
            if messages:
                msg = messages[0]
                numero = msg['from']

                if 'text' in msg:
                    texto_recebido = msg['text']['body']
                else:
                    texto_recebido = "Usuário enviou algo que não é texto."

                # IA gera a resposta baseada no que o usuário mandou
                resposta_ia = enviar_mensagem_ia(texto_recebido)
                texto_resposta = resposta_ia.get("resposta", "Desculpe, não entendi sua pergunta.")

                # Enviar a resposta no WhatsApp
                status, resposta_api = enviar_mensagem_whatsapp(numero, texto_resposta)
                print(f"✅ Mensagem enviada para {numero}: {texto_resposta}")

        except Exception as e:
            print("❌ Erro ao processar mensagem:", str(e))

        return jsonify({"status": "recebido"}), 200

if __name__ == "__main__":
    app.run(debug=True)
