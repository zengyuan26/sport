FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libz1 \
    libnss3 libnspr4 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN grep -v "face-recognition" requirements.txt > /tmp/reduced.txt && \
    pip install --no-cache-dir -r /tmp/reduced.txt gunicorn && \
    python -m playwright install chromium --with-deps

COPY . .

# CloudBase: CFS 持久化挂载到 /data
#   /data/fitness.db  — SQLite 数据库
#   /data/uploads/    — 二维码 + 照片（symlink 到 static/uploads）
ENV DATA_DIR=/data
RUN mkdir -p /data/uploads && \
    rm -rf /app/static/uploads && \
    ln -s /data/uploads /app/static/uploads

ENV PORT=8080
EXPOSE 8080

CMD gunicorn -b 0.0.0.0:${PORT} app:create_app\(\) --workers 2 --timeout 120
