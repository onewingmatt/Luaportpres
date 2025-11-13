FROM python:3.11-slim

WORKDIR /app

# Copy files first
COPY requirements.txt .
COPY app.py .
COPY president.html .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set Python to output logs immediately
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Health check - gives 30 seconds startup time
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/'); print('OK')" || exit 1

# Run app
CMD exec python -u app.py
