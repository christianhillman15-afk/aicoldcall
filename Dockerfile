FROM python:3.11-slim

# System deps: build tools for native wheels (e.g. onnxruntime used by Silero VAD).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir -e ".[postgres]"

EXPOSE 8000
CMD ["coldy", "serve"]
