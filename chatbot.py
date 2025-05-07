import openai
import requests
from datetime import datetime
import locale
import openpyxl
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify

# Configurações
load_dotenv()

try:
    locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
except:
    locale.setlocale(locale.LC_TIME, "")  # fallback

# Chaves de API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
EVOLUTION_TOKEN = os.getenv("EVOLUTION_TOKEN")
EVOLUTION_INSTANCE_ID = os.getenv("EVOLUTION_INSTANCE_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

client_openai = openai.Client(api_key=OPENAI_API_KEY)

# Inicializando o Flask
app = Flask(__name__)

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

# Endpoints Flask
@app.route('/mensagem', methods=['POST'])
def mensagem_ia():
    try:
        data = request.json
        mensagem = data.get('mensagem', '')
        
        if not mensagem:
            return jsonify({"erro": "Mensagem não fornecida."}), 400
        
        resposta_ia = enviar_mensagem_ia(mensagem)
        return jsonify(resposta_ia)
    
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/salvar_planilha', methods=['POST'])
def salvar_respostas():
    try:
        data = request.json
        dados = data.get('dados', [])
        
        if not dados:
            return jsonify({"erro": "Nenhum dado fornecido."}), 400
        
        resultado = salvar_planilha(dados)
        return jsonify(resultado)
    
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
