FROM node:22-bookworm-slim AS frontend
WORKDIR /build
RUN npm install --global pnpm@11
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/ /app/backend/
COPY --from=frontend /build/dist /app/frontend/dist
COPY deploy/start.sh /app/deploy/start.sh
RUN DJANGO_DEBUG=true VOTRIA_DEMO_MODE=false DJANGO_SECRET_KEY=build-only-placeholder python backend/manage.py collectstatic --noinput \
    && useradd --uid 10001 --create-home votria
USER votria
EXPOSE 10000
CMD ["sh", "/app/deploy/start.sh"]
