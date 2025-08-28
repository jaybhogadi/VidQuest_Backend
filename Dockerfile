# Python slim base
FROM python:3.10-slim

# System libs needed by faster-whisper/ctranslate2 + uploads + ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Workdir
WORKDIR /app

# (Optional) avoid .pyc files & ensure unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt /app/requirements.txt


RUN python -V && pip -V && echo "----- requirements.txt -----" && cat /app/requirements.txt

# Install Python deps (verbose so we see which one fails)
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -vvv --no-cache-dir -r /app/requirements.txt

# Install Python deps
# RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of your backend code
# (Make sure your FastAPI entrypoint is `main.py` with `app = FastAPI()`)
COPY . /app

# Expose port (Render/Railway/GCP etc. will honor $PORT, we default to 8000)
ENV PORT=8000

# Default command: uvicorn, 0.0.0.0 for Docker networking
CMD ["bash", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
