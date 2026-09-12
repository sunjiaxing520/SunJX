FROM node:22-alpine AS frontend
WORKDIR /build
COPY package*.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ENVIRONMENT=production
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && useradd --create-home app
COPY backend ./backend
COPY --from=frontend /build/dist ./dist
RUN mkdir .runtime && chown app:app .runtime
USER app
EXPOSE 8175
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8175"]
