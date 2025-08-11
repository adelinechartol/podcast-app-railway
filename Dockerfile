FROM python:3.10.11-slim

WORKDIR /app

# Install system dependencies required for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    gcc \
    g++ \
    libsndfile1 \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install all dependencies with extended timeout
RUN pip install --no-cache-dir --timeout 1000 -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p audio/responses podcasts/uploads podcasts/transcripts

# Start command
CMD gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1 --max-requests 100
