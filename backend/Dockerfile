# Backend runtime for Railway/Render; API and optional worker share private persistent storage.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app PORT=8000
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates util-linux && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 trust && useradd --uid 10001 --gid trust --create-home trust \
    && mkdir -p /var/lib/trust/history && chown -R trust:trust /var/lib/trust
COPY backend/requirements-runtime.txt ./requirements-runtime.txt
RUN pip install --no-cache-dir -r requirements-runtime.txt
# Libraries resolve user certificates/cache paths after the entrypoint drops privileges.
ENV HOME=/home/trust
COPY --chown=trust:trust backend/app ./app
COPY --chown=trust:trust backend/scripts ./scripts
COPY --chown=trust:trust backend/alembic ./alembic
COPY --chown=trust:trust backend/alembic.ini ./alembic.ini
RUN chmod +x /app/scripts/container_entrypoint.sh
ENTRYPOINT ["/app/scripts/container_entrypoint.sh"]
EXPOSE 8000
CMD ["python", "-m", "scripts.start_production"]
