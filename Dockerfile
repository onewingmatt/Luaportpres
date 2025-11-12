FROM python:3.11-slim

WORKDIR /app

# Copy and install requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && rm -rf /root/.cache

# Copy app files
COPY app.py .
COPY president.html .

# Expose port
EXPOSE 8080

# Simple health check
HEALTHCHECK --interval=5s --timeout=2s --start-period=3s --retries=2 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health').read()" || exit 1

# Run
CMD exec python -u app.py
