FROM python:3.11.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/

ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:8080", "--timeout", "120", "app:app"]
