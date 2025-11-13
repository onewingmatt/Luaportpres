FROM python:3.11-slim

WORKDIR /app

# Copy files early
COPY requirements.txt .
COPY app.py .
COPY president.html .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create saved_games directory
RUN mkdir -p /app/saved_games

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.connect(('127.0.0.1', 8080)); s.close()" || exit 1

# Start app with explicit port binding
CMD ["python", "-u", "app.py"]
