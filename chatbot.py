import os
import openai
from datetime import datetime
from twilio.rest import Client
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Obter as chaves de API da variável de ambiente
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# Inicializar o cliente da OpenAI
openai.api_key = OPENAI_API_KEY

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
        resposta = openai.ChatCompletion.create(
            model="gpt-4o-mini", 
            messages=[{"role": "user", "content": prompt_personalizado}],
            max_tokens=150,
            temperature=0.5
        )
        return resposta.choices[0].message['content'].strip()
    except Exception as e:
        return f"Erro na API do OpenAI: {e}"

# Função para enviar mensagem pelo WhatsApp (via Twilio)
def enviar_mensagem_whatsapp(mensagem, numero):
    client_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    mensagem_enviada = client_twilio.messages.create(
        body=mensagem,
        from_=TWILIO_WHATSAPP_NUMBER,  # Número da Twilio para WhatsApp
        to=f'whatsapp:{numero}'
    )
    return mensagem_enviada.sid

# Inicializando o Flask
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    # Recebe a mensagem do Twilio
    mensagem_usuario = request.form.get('Body')
    numero_usuario = request.form.get('From')

    if not mensagem_usuario or not numero_usuario:
        return Response(status=400)

    try:
        # Enviar a mensagem para o chatbot e obter a resposta
        resposta_chatbot = enviar_mensagem(mensagem_usuario)

        # Enviar a resposta de volta ao WhatsApp via Twilio
        enviar_mensagem_whatsapp(resposta_chatbot, numero_usuario)

        # Responder ao Twilio com uma resposta vazia (necessário para o Webhook)
        return Response("<Response></Response>", content_type='application/xml')

    except Exception as e:
        print(f"Erro ao processar a mensagem: {e}")
        return Response(status=500)

# Inicia a aplicação Flask
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
