from flask import Flask, request, jsonify
import openai
import requests
from datetime import datetime
import locale
import os
from dotenv import load_dotenv

# Configurações iniciais
load_dotenv()
app = Flask(__name__)

# Localização de tempo
try:
    locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
except locale.Error:
    locale.setlocale(locale.LC_TIME, "")

# Chaves de API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
EVOLUTION_INSTANCE_ID = os.getenv("EVOLUTION_INSTANCE_ID")
EVOLUTION_TOKEN = os.getenv("EVOLUTION_TOKEN")

# Cliente OpenAI
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
        response = requests.get("http://ip-api.com/json/")
        data = response.json()
        if data.get('status') == 'success':
            return {
                "pais": data['country'],
                "estado": data['regionName'],
                "cidade": data['city'],
                "ip": data['query']
            }
        return {"erro": "Não foi possível determinar sua localização."}
    except Exception as e:
        return {"erro": str(e)}

def obter_previsao_tempo(cidade, pais):
    if not cidade or not pais:
        return {"erro": "Cidade e país são obrigatórios."}
    
    url = (
        f"http://api.openweathermap.org/data/2.5/weather"
        f"?q={cidade},{pais}&appid={OPENWEATHER_API_KEY}&units=metric&lang=pt"
    )
    try:
        response = requests.get(url)
        dados = response.json()
        if response.status_code != 200:
            return {"erro": f"Não encontrei previsão para '{cidade}, {pais}'."}
        
        return {
            "cidade": cidade,
            "descricao": dados['weather'][0]['description'],
            "temperatura": dados['main']['temp'],
            "sensacao": dados['main']['feels_like'],
            "umidade": dados['main']['humidity'],
            "vento": dados['wind']['speed']
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

def enviar_resposta_whatsapp(numero, mensagem):
    url = f"https://api.z-api.io/instances/{EVOLUTION_INSTANCE_ID}/token/{EVOLUTION_TOKEN}/send-message"
    payload = {
        "phone": numero,
        "message": mensagem
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        return {"erro": str(e)}

# Rota de webhook para mensagens recebidas via Evolution API
@app.route("/webhook", methods=["POST"])
def webhook():
    dados = request.get_json()

    if not dados or "sender" not in dados or "message" not in dados or "body" not in dados["message"]:
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

# Rota de teste
@app.route("/", methods=["GET"])
def home():
    return "API Campo Inteligente está ativa.", 200

# Execução da aplicação
if __name__ == "__main__":
    app.run(port=5000, debug=True)
