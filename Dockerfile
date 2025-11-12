FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && rm -rf /root/.cache
COPY app.py president.html ./
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=2s --start-period=3s --retries=2 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080').read()" || exit 1
CMD exec python -u app.py
