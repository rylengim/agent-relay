FROM ghcr.io/astral-sh/uv:0.12.19 AS uv
FROM python:3.13-slim
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --python /usr/local/bin/python
RUN useradd --uid 10001 --create-home relay && mkdir /data && chown relay:relay /data
COPY *.py dashboard.html ./
ENV PATH="/app/.venv/bin:$PATH" RELAY_DATABASE_URL=sqlite:////data/agent-relay.db
USER relay
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=6 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
