FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN python -m pip install --upgrade pip && \
    python -m pip install .

ENV PORT=8765
EXPOSE 8765

CMD ["sh", "-c", "clicards-server --host 0.0.0.0 --port ${PORT}"]
