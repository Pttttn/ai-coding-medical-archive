FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY medical_ai ./medical_ai
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 ANONYMIZED_TELEMETRY=False
EXPOSE 8001 8002
CMD ["python", "-m", "medical_ai"]

