FROM python:3.9-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Seed initial database
RUN python database.py

EXPOSE 5000 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} app:app"]
