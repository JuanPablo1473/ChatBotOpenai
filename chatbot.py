from flask import Flask, request, jsonify
from datetime import datetime
import locale
import os
import requests
import openpyxl
from dotenv import load_dotenv
import openai

load_dotenv()

try:
    locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
except:
    locale.setlocale(locale.LC_TIME, "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
AUTH_KEY = os.getenv("AUTHENTICATION_API_KEY")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8081/manager/CampoIA")


openai.api_key = OPENAI_API_KEY
client_openai = openai

app = Flask(__name__)

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

def send_whatsapp_message(numero, mensagem):
    payload = {
        "number": numero,
        "text": mensagem
    }
    headers = {
        "Content-Type": "application/json",
        "apikey": AUTH_KEY
    }
    url = f"{EVOLUTION_API_URL}/message/send-text"
    try:
        resposta = requests.post(url, json=payload, headers=headers)
        print(f"Status do envio: {resposta.status_code}, Resposta: {resposta.text}")  # Log adicional
        return resposta.status_code, resposta.json()
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")
        return None, {"erro": str(e)}


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    mensagem = data.get("mensagem", "")

    if not mensagem:
        return jsonify({"erro": "Mensagem não fornecida."}), 400

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
        return jsonify({"resposta": conteudo})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/enviar-mensagem", methods=["POST"])
def route_enviar_mensagem():
    try:
        data = request.json
        numero = data.get("numero")
        mensagem = data.get("mensagem")

        if not numero or not mensagem:
            return jsonify({"erro": "Número e mensagem são obrigatórios."}), 400

        status_code, resposta_json = send_whatsapp_message(numero, mensagem)
        if status_code == 200:
            return jsonify({"status": "Mensagem enviada com sucesso!", "resposta": resposta_json}), 200
        else:
            return jsonify({"erro": "Erro ao enviar mensagem.", "detalhes": resposta_json}), status_code

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/clima", methods=["GET"])
def clima():
    local = obter_localizacao_via_ip()
    if "erro" in local:
        return jsonify(local), 400
    clima = obter_previsao_tempo(local.get("cidade"), local.get("pais"))
    return jsonify(clima)

@app.route("/clima-estendido", methods=["GET"])
def clima_estendido():
    local = obter_localizacao_via_ip()
    if "erro" in local:
        return jsonify(local), 400
    clima = obter_previsao_estendida(local.get("cidade"), local.get("pais"))
    return jsonify(clima)

@app.route("/salvar", methods=["POST"])
def salvar_planilha():
    try:
        dados = request.json.get("dados", [])
        if not dados:
            return jsonify({"erro": "Dados não fornecidos."}), 400
        arquivo = "respostas_agricultores_" + datetime.now().strftime("%Y%m%d%H%M%S") + ".xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Respostas"
        ws.append(["Nome", "Localização", "Data", "Dia da Semana"])
        for linha in dados:
            ws.append(linha)
        wb.save(arquivo)
        return jsonify({"arquivo_criado": arquivo})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return "API Campo Inteligente está online!"

@app.route("/webhook", methods=["POST"])
def webhook_route():
    try:
        data = request.json
        print(f"Dados recebidos: {data}")
        
        event = data.get('event')
        
        if event == 'messages.upsert':
            # Lógica para processar mensagens
            mensagem_recebida = data.get('data', {}).get('message', {}).get('conversation', '')
            print(f"Mensagem recebida: {mensagem_recebida}")

            # Respostas dependendo da mensagem
            if mensagem_recebida:
                if 'clima' in mensagem_recebida.lower():
                    local = obter_localizacao_via_ip()
                    clima = obter_previsao_tempo(local.get("cidade"), local.get("pais"))
                    resposta = f"Previsão do tempo em {local.get('cidade')}: {clima.get('descricao')}, Temp: {clima.get('temperatura')}°C, Sensação térmica: {clima.get('sensacao')}°C."
                elif 'previsão' in mensagem_recebida.lower():
                    local = obter_localizacao_via_ip()
                    clima_extendido = obter_previsao_estendida(local.get("cidade"), local.get("pais"))
                    resposta = f"Previsão estendida para os próximos dias: {clima_extendido.get('previsao')}"
                elif 'boa tarde' in mensagem_recebida.lower() or 'olá' in mensagem_recebida.lower():
                    resposta = "Olá! Como posso te ajudar hoje?"
                else:
                    resposta = "Desculpe, não entendi sua mensagem. Pode ser sobre clima ou previsão?"

                print(f"Resposta: {resposta}")
                
                numero = data.get('data', {}).get('key', {}).get('remoteJid', '')
                if numero:
                    # Verifique o número antes de enviar a mensagem
                    if not numero.endswith("@s.whatsapp.net"):
                        numero += "@s.whatsapp.net"
                    send_status, send_resp = send_whatsapp_message(numero, resposta)
                    print(f"Status do envio: {send_status}, resposta: {send_resp}")
                
                return jsonify({"status": "sucesso", "resposta": resposta}), 200

        elif event == 'chats.update':
            print("Evento chats.update recebido, mas não tratado.")
            return jsonify({"status": "Evento 'chats.update' recebido."}), 200
        
        else:
            print("Evento não reconhecido.")
            return jsonify({"erro": "Evento não reconhecido."}), 400
        
    except Exception as e:
        print(f"Erro: {str(e)}")
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
