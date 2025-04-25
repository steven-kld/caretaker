# syntax=docker/dockerfile:1.4

# --- Stage 1: Builder ---
    FROM python:3.10-bullseye AS builder

    # Avoid interactive prompts
    ENV DEBIAN_FRONTEND=noninteractive
    
    # Set working dir
    WORKDIR /src
    
    # Install system dependencies
    RUN apt-get update && apt-get install -y \
        ffmpeg \
        git \
        swig \
        && rm -rf /var/lib/apt/lists/*
    
    # Upgrade pip & wheel to avoid build issues
    RUN pip install --upgrade pip setuptools wheel
    
    # Copy requirements and install early
    COPY requirements.txt .
    
    # Install faiss-cpu first to ensure wheel install works
    RUN --mount=type=cache,target=/root/.cache/pip \
        pip install --prefer-binary faiss-cpu==1.8.0.post1
    
    # Then install the rest
    RUN --mount=type=cache,target=/root/.cache/pip \
        pip install --no-cache-dir -r requirements.txt
    
    # Copy source
    COPY . .
    
    CMD ["python3", "app.py"]
    
    
    # --- Optional Stage 2: Dev environment ---
    FROM builder as dev-envs
    
    RUN addgroup --system docker && \
        adduser --system --shell /bin/bash --ingroup docker vscode
    
    CMD ["python3", "app.py"]
    