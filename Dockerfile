FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    # dlib 编译依赖
    cmake build-essential libopenblas-dev liblapack-dev \
    # 运行时依赖
    libjpeg62-turbo libz1 \
    # playwright 依赖
    libnss3 libnspr4 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 先装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 验证 face_recognition 可用
RUN python -c "import face_recognition; print('face_recognition OK, version:', face_recognition.__version__)"

# 安装 playwright 浏览器
RUN python -m playwright install chromium --with-deps

# 清理编译工具（减小体积）
RUN apt-get update && apt-get remove -y cmake build-essential && \
    apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY . .

# CloudBase: CFS 持久化挂载到 /data
ENV DATA_DIR=/data
RUN mkdir -p /data/uploads && \
    rm -rf /app/static/uploads && \
    ln -s /data/uploads /app/static/uploads

ENV PORT=8080
EXPOSE 8080

CMD gunicorn -b 0.0.0.0:${PORT} app:create_app\(\) --workers 2 --timeout 120
