# ================================
# Base image: full Python runtime
# (required for LLMPot web control plane)
# ================================
FROM python:3.10 AS python-base

WORKDIR /app

# ----------------
# System deps
# ----------------
RUN apt-get update && apt-get install -y \
    gunicorn \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ----------------
# Python deps
# ----------------
COPY ./requirements.txt /app/requirements.txt
COPY ./emulator/requirements_web.txt /app/requirements_web.txt

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements_web.txt

# ----------------
# Environment
# ----------------
ARG MONGO_PWD

ENV PYTHONPATH="/app/emulator:/app/src"
ENV DOCKER_ENV="True"
ENV MONGO_PWD=${MONGO_PWD}

# ================================
# Final runtime image
# ================================
FROM python-base AS web

WORKDIR /app

# Application code
COPY ./src /app/src
COPY ./emulator /app/emulator

EXPOSE 8080

# ----------------
# Run web interface
# ----------------
CMD gunicorn \
    --workers 2 \
    --worker-connections 100 \
    -b 0.0.0.0:8080 \
    server.web_app:app
