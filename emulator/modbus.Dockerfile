# =====================================
# Base image: full Python runtime
# (required for stable Modbus emulator)
# =====================================
FROM python:3.10 AS python-base

WORKDIR /app

# ----------------
# System deps
# ----------------
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ----------------
# Python deps
# ----------------
COPY ./requirements.txt /app/requirements.txt
COPY ./emulator/requirements_modbus.txt /app/requirements_modbus.txt

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements_modbus.txt

# ----------------
# Environment
# ----------------
ENV PYTHONPATH="/app/emulator:/app/src"
ENV DOCKER_ENV="True"

ARG EXPERIMENT_PATH
ARG CHECKPOINT_PATH
ARG CHECKPOINT_PATH_TARGET
ARG EXPERIMENT
ARG MONGO_PWD

ENV EXPERIMENT_PATH=${EXPERIMENT_PATH}
ENV EXPERIMENT=${EXPERIMENT}
ENV MONGO_PWD=${MONGO_PWD}

# =====================================
# Model stage (kept for compatibility)
# =====================================
FROM python-base AS model
WORKDIR /app

# =====================================
# Final Modbus emulator container
# =====================================
FROM model AS modbus

COPY ./src /app/src
COPY ./emulator /app/emulator

# These are runtime experiment artifacts
COPY ${EXPERIMENT_PATH} /app/${EXPERIMENT_PATH}
COPY ${CHECKPOINT_PATH} /app/${CHECKPOINT_PATH_TARGET}

EXPOSE 5020

# ----------------
# Run Modbus honeypot
# ----------------
CMD ["python", "emulator/server/modbus_app.py"]
