FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py president.html ./
RUN mkdir -p saved_games
EXPOSE 8080
CMD exec python -u app.py
