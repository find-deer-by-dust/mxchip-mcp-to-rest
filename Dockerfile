FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --uid 10001 app

COPY requirements.txt main.py ./
# Reuse the launcher's installer and fingerprint so startup needs no downloads.
RUN python -c "from main import ensure_dependencies; ensure_dependencies()"

COPY dehumidifier_mcp.py LICENSE ./

USER app
EXPOSE 8000

CMD ["python", "main.py"]
