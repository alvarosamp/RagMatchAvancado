FROM python:3.10-slim

WORKDIR /app

# Dependências de sistema necessárias para OpenCV (cv2) usado pelo docling/tableformer
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxcb1 \
    libxrender1 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

#Melhora experiencia de instalação
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .

# Instala dependências listadas em requirements.txt (inclui uvicorn)
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

#Reload para dev -> Produção muda
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]