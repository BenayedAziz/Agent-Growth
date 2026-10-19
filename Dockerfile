# Image de production pour Railway (ou tout hébergeur de conteneurs).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # La base vit sur le volume persistant monté en /data. Sans volume, elle
    # serait effacée à chaque déploiement.
    AG_DB=/data/console.db

# Lighthouse — le moteur de PageSpeed Insights — mesure la vitesse quand
# l'API de Google refuse (quota). Il lui faut Node et Chromium.
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium nodejs npm \
 && npm install -g lighthouse@12.8.2 \
 && rm -rf /var/lib/apt/lists/* /root/.npm
ENV CHROME_PATH=/usr/bin/chromium

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install .

EXPOSE 8000
# Une seule instance : la base est SQLite. Railway fournit $PORT.
CMD ["sh", "-c", "exec ag run --host 0.0.0.0 --port ${PORT:-8000}"]
