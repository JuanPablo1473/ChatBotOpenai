import os
import openai
import openpyxl
from datetime import datetime
import locale
from twilio.rest import Client
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Definir a localidade para português do Brasil
locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")

# Obter as chaves de API da variável de ambiente
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# Inicializar o cliente da OpenAI
openai.api_key = OPENAI_API_KEY

# Inicializar o cliente Twilio
client_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Função para obter a data e hora no formato desejado
def obter_data_hora():
    data_atual = datetime.now()
    data_formatada = data_atual.strftime("%d de %B de %Y")  # Ex: 24 de março de 2025
    dia_da_semana = data_atual.strftime("%A")  # Ex: domingo
    return data_formatada, dia_da_semana

# Função para enviar mensagens para o modelo GPT
def enviar_mensagem(mensagem):
    prompt_personalizado = f"Você está conversando com um agricultor no sistema do Campo Inteligente. Responda de forma clara e objetiva sobre cadastro, funcionalidades do sistema, ou uso agrícola. Pergunta: {mensagem}"
    try:
        # Corrigido para utilizar a sintaxe correta com chat.completions
        resposta = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_personalizado}],
            max_tokens=150,
            temperature=0.5
        )
        return resposta.choices[0].message['content'].strip()  # Corrigido para acessar a resposta corretamente
    except Exception as e:
        return f"Erro na API do OpenAI: {e}"

# Função para enviar mensagem pelo WhatsApp (via Twilio)
def enviar_mensagem_whatsapp(mensagem, numero):
    mensagem_enviada = client_twilio.messages.create(
        body=mensagem,
        from_=f'whatsapp:{TWILIO_WHATSAPP_NUMBER}',  # Número da Twilio para WhatsApp
        to=f'whatsapp:{numero}'
    )
    return mensagem_enviada.sid

# Função para lidar com a resposta no WhatsApp
def processar_resposta_whatsapp(mensagem):
    resposta = enviar_mensagem(mensagem)
    return resposta

# Criando a aplicação Flask
app = Flask(__name__)

# Rota que lida com as mensagens recebidas no WhatsApp via Twilio
@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '')

    # Processa a resposta do OpenAI
    if incoming_msg:
        resposta = processar_resposta_whatsapp(incoming_msg)
    else:
        resposta = "Desculpe, não entendi. Pode repetir?"

    # Responde com a mensagem gerada pelo OpenAI
    resp = MessagingResponse()
    resp.message(resposta)
    return str(resp)

# Função para enviar um WhatsApp diretamente
@app.route("/enviar_whatsapp", methods=["POST"])
def enviar_whatsapp():
    numero = request.json.get("numero")
    mensagem = request.json.get("mensagem")
    if numero and mensagem:
        sid = enviar_mensagem_whatsapp(mensagem, numero)
        return jsonify({"sid": sid, "status": "Mensagem enviada com sucesso!"})
    return jsonify({"status": "Erro", "message": "Número ou mensagem não fornecidos."}), 400

# Função para rodar a aplicação Flask
if __name__ == "__main__":
    app.run(debug=True)
