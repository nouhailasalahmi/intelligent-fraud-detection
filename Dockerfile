FROM python:3.11-slim

# Éviter la mise en cache des bytecode et assurer le flush des logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances système pour psycopg2 et compilation si nécessaire
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installation des packages Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source et des modèles
COPY . .

# Commande par défaut (peut être surchargée dans docker-compose)
CMD ["python", "consumer.py"]
