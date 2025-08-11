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
# Copy run script
COPY run.py .

# Use Python to start the app
# Railway typically uses port 8080 internally
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--timeout", "120", "--workers", "1"]
