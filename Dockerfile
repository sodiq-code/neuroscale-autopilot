FROM python:3.11-slim

LABEL maintainer="Sodiq Jimoh <sodiqjimoh80@gmail.com>"
LABEL description="NeuroScale Autopilot — Qwen-powered K8s self-healing agent"

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Non-root user for security
RUN useradd -m -u 1000 autopilot && chown -R autopilot:autopilot /app
USER autopilot

# Default env
ENV DRY_RUN=true \
    POLL_INTERVAL_SECONDS=30 \
    QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "main.py"]
