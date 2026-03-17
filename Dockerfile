# ============================================================
# AI 内容运营助手 - 阿里云 SAE 部署专用 Dockerfile
# ============================================================
# 
# 使用方法：
#   docker build --platform linux/amd64 -t ai-content-assistant:v1.0.0 .
#
# 本地测试：
#   docker run --env-file .env -p 8000:8000 ai-content-assistant:v1.0.0
#
# ============================================================

FROM python:3.13-slim

# ---- 系统依赖 ----
# libpq-dev: PostgreSQL 客户端库（asyncpg / psycopg 编译依赖）
# gcc: C 编译器（部分 Python 包需要编译原生扩展）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ---- 工作目录 ----
WORKDIR /app

# ---- 安装 Python 依赖（利用 Docker 缓存层） ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- 复制业务代码 ----
COPY app/ ./app/
COPY scripts/ ./scripts/

# ---- 创建必要的目录 ----
# static: 生成的图片存储目录
# logs: 日志文件目录
RUN mkdir -p /app/static /app/logs

# ---- 环境变量默认值 ----
# 服务监听端口（SAE 通过此端口转发流量）
ENV PORT=8000
# 关闭 debug 模式
ENV DEBUG=false
# 日志级别
ENV LOG_LEVEL=INFO
# 日志输出到控制台（SAE 自动采集 stdout）
ENV LOG_CONSOLE=true
ENV LOG_JSON=true

# ---- 健康检查 ----
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# ---- 暴露端口 ----
EXPOSE ${PORT}

# ---- 启动命令 ----
# 使用 uvicorn 启动 FastAPI 应用
# --workers 2: 适合 1核2G 的 SAE 实例
CMD uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --workers 2 \
    --log-level info
