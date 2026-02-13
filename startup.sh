#!/usr/bin/env bash
set -euo pipefail
 
export DEBIAN_FRONTEND=noninteractive
 
apt-get update
apt-get install -y --no-install-recommends \
  tesseract-ocr \
  tesseract-ocr-spa \
  libglib2.0-0 \
  libgl1 \
  libgomp1
 
rm -rf /var/lib/apt/lists/*
 
# Run Gunicorn with extended timeout and optimized worker configuration
# --timeout 300: Allow up to 5 minutes for processing large files and LLM responses
# --workers 4: Number of worker processes (adjust based on CPU cores)
# --worker-class gevent: Use async workers for better I/O handling
# --worker-connections 1000: Max concurrent connections per worker
# --keep-alive 5: Keep connections alive for 5 seconds
# --graceful-timeout 120: Allow 2 minutes for graceful worker restart
# --max-requests 1000: Restart workers after 1000 requests to prevent memory leaks
# --max-requests-jitter 50: Add randomness to prevent all workers restarting simultaneously
exec gunicorn -b 0.0.0.0:${PORT:-8000} \
  --timeout 300 \
  --workers 4 \
  --worker-class gevent \
  --worker-connections 1000 \
  --keep-alive 5 \
  --graceful-timeout 120 \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  api.server:app
  api.server:app
