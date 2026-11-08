# --- 1) build do frontend ---
FROM node:22.12.0-alpine AS front
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2) app (API + agentes + RH simulado + frontend estático) ---
FROM python:3.11.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DB_PATH=/data/subsidia.db PORT=8000
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY eval/ eval/
COPY seed/ seed/
COPY --from=front /front/dist frontend/dist
RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8000
# LLM_API_KEY vem do ambiente da plataforma (nunca no build).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
