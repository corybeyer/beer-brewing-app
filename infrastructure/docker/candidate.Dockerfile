FROM node:24-bookworm-slim AS web-build
WORKDIR /build
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/ui/package.json ./packages/ui/package.json
COPY packages/design-system/package.json ./packages/design-system/package.json
COPY packages/communications/package.json ./packages/communications/package.json
RUN npm ci
COPY apps/web/ ./apps/web/
COPY packages/ui/ ./packages/ui/
COPY packages/design-system/ ./packages/design-system/
COPY packages/communications/ ./packages/communications/
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv/brewery
COPY requirements.lock pyproject.toml ./
COPY apps/api/ ./apps/api/
COPY packages/config/ ./packages/config/
COPY packages/database/src/ ./packages/database/src/
COPY --from=web-build /build/apps/web/dist/ ./web/
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip install --no-cache-dir --no-deps --no-build-isolation . \
    && useradd --create-home --uid 10001 brewery \
    && chmod -R a+rX /srv/brewery
ENV WEB_ASSETS_DIRECTORY=/srv/brewery/web
USER brewery
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/readiness', timeout=4)"
CMD ["python", "-m", "uvicorn", "brewery_api.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
