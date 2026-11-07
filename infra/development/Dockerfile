FROM python:3.12-slim

WORKDIR /srv/brewery
COPY requirements.lock pyproject.toml alembic.ini ./
COPY app/ ./app/
COPY infra/database/ ./infra/database/
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip install --no-cache-dir --no-deps --no-build-isolation . \
    && useradd --create-home --uid 10001 brewery \
    && chmod -R a+rX /srv/brewery
USER brewery
EXPOSE 8081
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/api/v1/readiness', timeout=4)"
CMD ["python", "-m", "uvicorn", "brewery.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8081"]
