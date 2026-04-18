FROM python:3.12-slim

  ENV PYTHONDONTWRITEBYTECODE=1
  ENV PYTHONUNBUFFERED=1

  WORKDIR /app

  RUN apt-get update && apt-get install -y \
      build-essential \
      gcc \
      libglib2.0-0 \
      libsm6 \
      libxext6 \
      libxrender1 \
      libgomp1 \
      libgl1 \
      tesseract-ocr \
      curl \
   && rm -rf /var/lib/apt/lists/*

  COPY requirements.txt .
  RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
      pip install --no-cache-dir -r requirements.txt

  COPY . .

  CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT"]