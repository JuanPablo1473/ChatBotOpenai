# 1. Usar uma imagem base oficial do Python
FROM python:3.9-slim

# 2. Definir o diretório de trabalho dentro do contêiner
WORKDIR /app

# 3. Copiar o arquivo de dependências
COPY requirements.txt requirements.txt

# 4. Instalar as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar todo o código do seu projeto para dentro do contêiner
# Isso inclui o seu chatbot.py
COPY . .

# 6. Expor a porta que o Gunicorn/Flask vai usar
EXPOSE 5000

# 7. O comando para rodar a aplicação quando o contêiner iniciar
# Esta é a linha que efetivamente executa o seu "chatbot.py"
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "chatbot:app"]
