FROM python:3.10-slim

WORKDIR /app

#Melhora experiencia de instalação
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .

COPY app ./app

EXPOSE 8000

#Reload para dev -> Produção muda
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]