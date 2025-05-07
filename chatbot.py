from flask import Flask, request, jsonify
import openai
import requests
from datetime import datetime
import locale
import os
from dotenv import load_dotenv

# Configurações
load_dotenv()
app = Flask(__name__)

try:
    locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
except:
    locale.setlocale(locale.LC_TIME, "")  # fallback

# Chaves
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
EVOLUTION_INSTANCE_ID = os.getenv("EVOLUTION_INSTANCE_ID")
EVOLUTION_TOKEN = os.getenv("EVOLUTION_TOKEN")

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

def enviar_mensagem_ia(mensagem):
    try:
        local = obter_localizacao_via_ip()
        clima = obter_previsao_tempo(local.get("cidade", "Salvador"), local.get("pais", "BR"))
        prompt = (
            "Você é um assistente agrícola no sistema Campo Inteligente.\n"
            f"📍 Local: {local}\n"
            f"🌦️ Clima: {clima}\n"
            f"❓ Pergunta: {mensagem}."
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

def enviar_resposta_whatsapp(numero, mensagem):
    url = f"https://api.z-api.io/instances/{EVOLUTION_INSTANCE_ID}/token/{EVOLUTION_TOKEN}/send-message"
    payload = {
        "phone": numero,
        "message": mensagem
    }
    try:
        r = requests.post(url, json=payload)
        return r.json()
    except Exception as e:
        return {"erro": str(e)}

# Rota de webhook para Evolution API
@app.route("/webhook", methods=["POST"])
def webhook():
    dados = request.get_json()

    # Validando se os dados esperados estão presentes
    if "sender" not in dados or "message" not in dados or "body" not in dados["message"]:
        return jsonify({"erro": "Dados inválidos no webhook."}), 400

    try:
        numero = dados["sender"]
        mensagem_usuario = dados["message"]["body"]
        resposta_ia = enviar_mensagem_ia(mensagem_usuario)
        texto_resposta = resposta_ia.get("resposta", "Desculpe, não consegui entender sua pergunta.")
        enviar_resposta_whatsapp(numero, texto_resposta)
        return jsonify({"status": "mensagem enviada"}), 200
    except Exception as e:
        return jsonify({"erro": f"Erro ao processar a solicitação: {str(e)}"}), 400

# Rota base para teste simples
@app.route("/", methods=["GET"])
def home():
    return "API Campo Inteligente está ativa.", 200

if __name__ == "__main__":
    app.run(port=5000, debug=True)
