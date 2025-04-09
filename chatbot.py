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
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE_ID = "85bea790-97cf-4208-a33a-2105dec71b2e"

client_openai = openai.Client(api_key=OPENAI_API_KEY)

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

def obter_localizacao_via_ip():
    try:
        r = requests.get("http://ip-api.com/json/")
        d = r.json()
        if d['status'] == 'success':
            return {
                "pais": d['country'],
                "estado": d['regionName'],
                "cidade": d['city'],
                "ip": d['query']
            }
        return {"erro": "Não foi possível determinar sua localização."}
    except Exception as e:
        return {"erro": str(e)}

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

def enviar_mensagem_evolution(numero, mensagem):
    try:
        url = f"http://localhost:8081/manager/instance/{EVOLUTION_INSTANCE_ID}/sqs"
        payload = {"number": numero, "message": mensagem}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers)
        return {"status": response.status_code, "mensagem": response.text}
    except Exception as e:
        return {"erro": str(e)}

def enviar_mensagem_ia(mensagem):
    try:
        local = obter_localizacao_via_ip()
        clima = obter_previsao_tempo(local.get("cidade", "Salvador"), local.get("pais", "BR"))
        prompt = (
            "Você é um assistente agrícola no sistema Campo Inteligente.\n"
            f"📍 Local: {local}\n"
            f"🌦️ Clima: {clima}\n"
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
@app.route("/")
def home():
    return {"mensagem": "🚜 API Campo Inteligente Rodando!"}

@app.route("/localizacao", methods=["GET"])
def localizacao():
    return jsonify(obter_localizacao_via_ip())

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
    return jsonify(enviar_mensagem_ia(mensagem))

@app.route("/enviar_evolution", methods=["POST"])
def enviar_evolution():
    data = request.json
    numero = data.get("numero")
    mensagem = data.get("mensagem")
    return jsonify(enviar_mensagem_evolution(numero, mensagem))

@app.route("/salvar_agricultores", methods=["POST"])
def salvar_agricultores():
    dados = request.json.get("dados", [])
    return jsonify(salvar_planilha(dados))

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("🔔 Webhook recebido:", data)

        if data.get("event") == "messages.upsert":
            mensagem_info = data.get("data", {})
            mensagem = mensagem_info.get("message", {})

            if "conversation" in mensagem:
                mensagem_texto = mensagem.get("conversation")
            elif "extendedTextMessage" in mensagem:
                mensagem_texto = mensagem["extendedTextMessage"].get("text")
            else:
                mensagem_texto = ""

            numero_completo = mensagem_info.get("key", {}).get("remoteJid", "")
            if not numero_completo.endswith("@s.whatsapp.net"):
                print("⚠️ Ignorando mensagem de grupo ou formato inválido:", numero_completo)
                return jsonify({"status": "ignorado"})

            numero_formatado = numero_completo.split('@')[0]

            if mensagem_texto and numero_formatado:
                print(f"📩 Mensagem recebida de {numero_formatado}: {mensagem_texto}")

                resposta_ia = enviar_mensagem_ia(mensagem_texto)
                print("🔎 Resposta da IA:", resposta_ia)

                resposta_final = resposta_ia.get("resposta", "Desculpe, não entendi sua pergunta.")
                envio = enviar_mensagem_evolution(numero_formatado, resposta_final)
                print("📤 Resultado do envio Evolution:", envio)

        return jsonify({"status": "mensagem processada com sucesso"})

    except Exception as e:
        print("❌ Erro ao processar webhook:", str(e))
        return jsonify({"erro": str(e)}), 500

# Início da aplicação
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
