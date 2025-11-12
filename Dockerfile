FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && rm -rf /root/.cache
COPY app.py president.html ./
EXPOSE 8080
CMD exec python -u app.py
