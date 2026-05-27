FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# DB on a Railway volume mounted at /data so history survives restarts.
ENV DB_PATH=/data/bot.db
RUN mkdir -p /data

CMD ["python", "bot.py"]
