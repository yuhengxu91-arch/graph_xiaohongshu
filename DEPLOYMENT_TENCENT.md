# AI 内容运营助手 — 腾讯云轻量服务器部署指南

> 本文档记录了将 v1 版本部署到 **腾讯云轻量应用服务器** 的完整流程。
> 架构：**Nginx 同时服务前端静态文件和后端 API**，全部在同一台服务器上。

---

## 📐 部署架构

```
                        用户浏览器
                            │
                     http://119.91.198.219
                            │
         ┌──────────────────▼──────────────────────┐
         │       腾讯云轻量应用服务器                  │
         │       119.91.198.219                     │
         │       4核 / 4GB / 40GB SSD               │
         │                                          │
         │   Nginx (:80)                            │
         │   ├── /              → 前端静态文件 (SPA) │
         │   ├── /api/*         → FastAPI :8000     │
         │   ├── /static/*      → FastAPI :8000     │
         │   ├── /health        → FastAPI :8000     │
         │   └── /docs          → FastAPI :8000     │
         │                                          │
         │   Docker Compose                         │
         │   ├── xhs-backend (FastAPI :8000)        │
         │   │   └── 127.0.0.1:8000                 │
         │   └── xhs-postgres (PostgreSQL 16)       │
         │       └── 127.0.0.1:5432                 │
         │                                          │
         │   前端构建产物                              │
         │   └── /opt/graph_xiaohongshu/frontend-dist │
         └──────────────────────────────────────────┘
```

### 与阿里云 SAE 方案的区别

| 维度 | 腾讯云轻量（本方案） | 阿里云 SAE（DEPLOYMENT.md） |
|------|--------------------|-----------------------------|
| 计算 | 固定规格 ECS | Serverless 弹性伸缩 |
| 数据库 | Docker 容器内 PostgreSQL | RDS Serverless（托管） |
| 前端 | Nginx 静态文件服务 | OSS + CDN |
| HTTPS | 需自行配置 Certbot | CLB + SSL 证书 |
| 成本 | ~¥50-100/月（固定） | ~¥150-200/月（按量） |
| 运维 | 需自行管理服务器 | 全托管，零运维 |
| 适用 | 个人项目 / 开发测试 | 正式生产环境 |

---

## 1️⃣ 服务器环境准备

### 1.1 购买服务器

- **平台**：[腾讯云轻量应用服务器](https://cloud.tencent.com/product/lighthouse)
- **镜像**：Ubuntu 22.04 + Docker（官方应用镜像 `Docker26-m7u0`）
- **配置**：4 核 CPU / 4GB 内存 / 40GB SSD
- **地域**：广州

### 1.2 登录服务器

```bash
ssh ubuntu@119.91.198.219
```

### 1.3 验证 Docker 环境

```bash
docker --version         # Docker 26+
docker compose version   # Docker Compose v2+
```

### 1.4 安装 Node.js（前端构建需要）

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v   # v20.x
npm -v    # 10.x
```

### 1.5 配置文件权限

```bash
sudo mkdir -p /opt/graph_xiaohongshu
sudo chown -R ubuntu:ubuntu /opt/graph_xiaohongshu
```

---

## 2️⃣ 后端部署（Docker Compose）

### 2.1 拉取代码

```bash
cd /opt
git clone https://gitee.com/你的用户名/graph_xiaohongshu.git
cd graph_xiaohongshu
git checkout v1
```

> ⚠️ 如果 `git checkout v1` 时有文件冲突，先执行：
> ```bash
> git stash
> git checkout v1
> ```

### 2.2 创建 Dockerfile

```dockerfile
# /opt/graph_xiaohongshu/Dockerfile
FROM python:3.13-slim

WORKDIR /app

# 使用腾讯云镜像加速（国内服务器必须）
RUN sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（利用 Docker 缓存层 + 腾讯云 PyPI 镜像）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.cloud.tencent.com/pypi/simple/ \
    --trusted-host mirrors.cloud.tencent.com

# 复制业务代码
COPY . .

# 创建日志目录
RUN mkdir -p logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.3 创建 docker-compose.yml

```yaml
# /opt/graph_xiaohongshu/docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    container_name: xhs-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: Xhs2026Secure!
      POSTGRES_DB: langgraph_db
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: .
    container_name: xhs-backend
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    env_file:
      - .env.production
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./logs:/app/logs
    deploy:
      resources:
        limits:
          memory: 2G

volumes:
  pgdata:
```

### 2.4 创建生产环境配置

```bash
cat > /opt/graph_xiaohongshu/.env.production << 'EOF'
# ===== 数据库 =====
DATABASE_URL=postgresql+asyncpg://postgres:Xhs2026Secure!@postgres:5432/langgraph_db
POSTGRES_URI=postgresql://postgres:Xhs2026Secure!@postgres:5432/langgraph_db

# ===== 应用配置 =====
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# ===== JWT =====
JWT_SECRET_KEY=替换为强随机字符串   # 用 openssl rand -hex 32 生成
JWT_ALGORITHM=HS256

# ===== LLM API Keys =====
LLM_API_KEY=你的火山引擎API密钥

# ===== 图片生成 =====
IMAGE_API_KEY=你的Gemini密钥

# ===== CORS =====
CORS_ORIGINS=http://119.91.198.219,http://localhost:5173
EOF
```

> ⚠️ `.env.production` 已在 `.gitignore` 中，不会被提交到 Git。

### 2.5 构建并启动

```bash
cd /opt/graph_xiaohongshu
docker compose up -d --build
```

> 首次构建约需 3-5 分钟（取决于网络速度和依赖数量）。

### 2.6 验证

```bash
# 检查容器状态（两个都应该是 healthy）
docker ps

# 测试健康检查
curl http://localhost:8000/health
# 期望输出: {"status":"healthy","service":"AI内容运营助手"}
```

### 2.7 数据库字段补齐（如需要）

如果登录/注册时出现 `column users.xxx does not exist` 错误：

```bash
docker exec -it xhs-postgres psql -U postgres -d langgraph_db -c "
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname VARCHAR(100) DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
"
docker restart xhs-backend
```

---

## 3️⃣ 前端部署（服务器上构建）

前端直接在服务器上构建，Nginx 以静态文件形式服务，避免 Vercel HTTPS/HTTP 混合内容问题。

### 3.1 构建前端

```bash
cd /opt/graph_xiaohongshu/frontend

# 安装依赖
npm install

# 构建（VITE_API_BASE_URL 留空，走相对路径）
VITE_API_BASE_URL= npm run build

# 复制构建产物到 Nginx 服务目录
cp -r dist/ /opt/graph_xiaohongshu/frontend-dist/
```

### 3.2 后续更新前端

代码更新后重新构建：

```bash
cd /opt/graph_xiaohongshu
git pull origin v1
cd frontend
npm install
VITE_API_BASE_URL= npm run build
cp -r dist/ /opt/graph_xiaohongshu/frontend-dist/
# Nginx 无需重载，静态文件直接生效
```

---

## 4️⃣ Nginx 反向代理

Nginx 负责两件事：**服务前端静态文件** + **反向代理后端 API**。

### 4.1 安装 Nginx

```bash
sudo apt install -y nginx
```

### 4.2 配置站点

```bash
sudo tee /etc/nginx/sites-available/api << 'EOF'
server {
    listen 80 default_server;
    server_name _;

    # 前端静态文件
    root /opt/graph_xiaohongshu/frontend-dist;
    index index.html;

    # API 请求转发到后端
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE 流式支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # 生成的配图（存储在后端容器内）
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        expires 7d;
    }

    # 后端其他路由
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
    }

    # SPA 回退（Vue Router History 模式）
    location / {
        try_files $uri $uri/ /index.html;
    }

    client_max_body_size 20M;
}
EOF

sudo ln -sf /etc/nginx/sites-available/api /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

> **配置要点**：
> - `root` 指向前端构建产物目录
> - `/api/` 和 `/static/` 转发到后端容器
> - `/api/` 开启 `proxy_buffering off` 支持 SSE 流式响应
> - `try_files` 实现 SPA 路由回退，解决刷新 404 问题

### 4.3 开放防火墙

在 [腾讯云轻量应用服务器控制台](https://console.cloud.tencent.com/lighthouse) → 实例 → **防火墙** → 添加规则：

| 协议 | 端口 | 说明 |
|------|------|------|
| TCP  | 80   | HTTP |
| TCP  | 443  | HTTPS（后续绑域名时用） |

> ⚠️ **不要开放** 5432（数据库）和 8000（直连后端）端口。

### 4.4 验证

```bash
# 后端健康检查
curl http://119.91.198.219/health
# 期望输出: {"status":"healthy","service":"AI内容运营助手"}

# 前端页面
curl -I http://119.91.198.219/
# 期望: HTTP/1.1 200 OK

# SPA 路由
curl -I http://119.91.198.219/workflow
# 期望: HTTP/1.1 200 OK（非 404）
```

浏览器打开 `http://119.91.198.219` 即可访问完整应用。

---

## 5️⃣ 安全与端口规划

### 端口规划

| 端口 | 绑定地址 | 用途 | 外网可访问 |
|------|---------|------|-----------|
| 80 | 0.0.0.0 | Nginx HTTP | ✅ |
| 443 | 0.0.0.0 | Nginx HTTPS | ✅（绑域名后） |
| 8000 | 127.0.0.1 | FastAPI 后端 | ❌ |
| 5432 | 127.0.0.1 | PostgreSQL | ❌ |

### 安全清单

- [x] 数据库端口仅内网可达（127.0.0.1 绑定）
- [x] 后端端口仅通过 Nginx 转发
- [x] 前后端同源，无跨域问题
- [ ] JWT 密钥替换为强随机字符串（`openssl rand -hex 32`）
- [ ] 绑定域名 + HTTPS（`certbot --nginx`）
- [ ] 数据库定期备份

---

## 6️⃣ HTTPS 配置（绑域名后）

### 6.1 添加 DNS 记录

在域名服务商（如腾讯云 DNSPod）添加 A 记录：

```
xhs.yourdomain.com → 119.91.198.219
```

### 6.2 修改 Nginx server_name

```bash
sudo sed -i 's/server_name _;/server_name xhs.yourdomain.com;/' /etc/nginx/sites-available/api
sudo nginx -t && sudo systemctl reload nginx
```

### 6.3 申请 SSL 证书

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d xhs.yourdomain.com
```

Certbot 会自动修改 Nginx 配置，添加 443 监听和证书路径。

### 6.4 更新 CORS

更新 `.env.production` 中的 CORS_ORIGINS 为 HTTPS 域名：

```bash
# .env.production
CORS_ORIGINS=https://xhs.yourdomain.com,http://localhost:5173
```

然后重启后端：

```bash
docker restart xhs-backend
```

---

## 7️⃣ 多应用扩展

同一服务器部署第二个应用时，修改 Nginx 配置：

### 方案 A：子域名路由（需域名）

```nginx
# /etc/nginx/sites-available/app-xhs
server {
    listen 80;
    server_name xhs.yourdomain.com;
    root /opt/graph_xiaohongshu/frontend-dist;

    location /api/ { proxy_pass http://127.0.0.1:8000; ... }
    location /static/ { proxy_pass http://127.0.0.1:8000; ... }
    location / { try_files $uri $uri/ /index.html; }
}

# /etc/nginx/sites-available/app-other
server {
    listen 80;
    server_name other.yourdomain.com;
    root /opt/other-app/frontend-dist;

    location /api/ { proxy_pass http://127.0.0.1:8001; ... }
    location / { try_files $uri $uri/ /index.html; }
}
```

### 方案 B：路径路由（无域名）

```nginx
server {
    listen 80 default_server;

    # 应用1：小红书助手
    location /xhs/ {
        alias /opt/graph_xiaohongshu/frontend-dist/;
        try_files $uri $uri/ /xhs/index.html;
    }
    location /xhs/api/ { proxy_pass http://127.0.0.1:8000/api/; }

    # 应用2：其他应用
    location /app2/ {
        alias /opt/other-app/frontend-dist/;
        try_files $uri $uri/ /app2/index.html;
    }
    location /app2/api/ { proxy_pass http://127.0.0.1:8001/api/; }
}
```

**要点**：每个应用独立目录 + 独立 docker-compose + 不同端口，可共享 PostgreSQL（不同数据库）。

---

## 8️⃣ 常用运维命令

```bash
# ===== 容器管理 =====
docker ps                                    # 查看容器状态
docker logs xhs-backend --tail 100 -f        # 实时查看后端日志
docker restart xhs-backend                   # 重启后端
docker compose up -d --build                 # 重新构建并启动
docker compose down                          # 停止所有容器

# ===== 数据库 =====
docker exec -it xhs-postgres psql -U postgres -d langgraph_db   # 进入数据库
docker exec xhs-postgres pg_dump -U postgres langgraph_db > backup_$(date +%Y%m%d).sql  # 备份

# ===== 前端更新 =====
cd /opt/graph_xiaohongshu/frontend
git pull origin v1
npm install
VITE_API_BASE_URL= npm run build
cp -r dist/ /opt/graph_xiaohongshu/frontend-dist/

# ===== 磁盘 =====
df -h                                        # 查看磁盘空间
docker system df                             # Docker 占用空间
docker system prune -a                       # 清理未使用的镜像和容器

# ===== Nginx =====
sudo nginx -t                                # 测试配置
sudo systemctl reload nginx                  # 重载配置
sudo tail -f /var/log/nginx/error.log        # 查看错误日志
```

---

## 9️⃣ 后续待办

| 优先级 | 事项 | 说明 |
|-------|------|------|
| 🔴 高 | 替换 JWT 密钥 | `openssl rand -hex 32` 生成强随机字符串 |
| 🔴 高 | 绑定域名 + HTTPS | `certbot --nginx`，参考第 6 节 |
| 🟡 中 | 配置 Swap | `sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` |
| 🟡 中 | 数据库自动备份 | `crontab -e` 添加每日备份任务 |
| 🟢 低 | 监控告警 | uptime-kuma 或腾讯云自带监控 |
| 🟢 低 | CI/CD | Gitee WebHook + 自动构建部署 |

---

## 常见问题

### Q1: Docker 构建时 pip install 很慢或报错

腾讯云 PyPI 镜像可能同步延迟。解决方案：

```dockerfile
# Dockerfile 中改用阿里云镜像
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com
```

### Q2: 浏览器刷新后页面 404

Nginx 配置中缺少 SPA 回退。确保 `location /` 包含：

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

### Q3: 图片不显示（配图 1/2/3 为空白）

Nginx 缺少 `/static/` 代理配置。添加：

```nginx
location /static/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    expires 7d;
}
```

### Q4: 后端返回 500，日志显示 `column xxx does not exist`

数据库表结构与代码不匹配。执行 2.7 步骤补齐缺失字段。

### Q5: Nginx 返回 500 Internal Server Error

通常是 `root` 目录不存在或权限问题：

```bash
# 确认前端构建产物目录存在
ls /opt/graph_xiaohongshu/frontend-dist/index.html

# 确认权限
sudo chown -R ubuntu:ubuntu /opt/graph_xiaohongshu/frontend-dist/
```

### Q6: Vercel 方案的局限性（为什么不用 Vercel）

最初尝试过 Vercel 托管前端，但遇到两个问题：

1. **Mixed Content**：Vercel 强制 HTTPS，但后端 API 是 HTTP（IP 模式无法配 HTTPS），浏览器拦截请求
2. **Rewrites 超时**：通过 Vercel Rewrites 代理 API 请求（绕过 Mixed Content），但免费版有 **10 秒超时限制**，LLM 生成等长时间请求会失败（`ROUTER_EXTERNAL_TARGET_CONNECTION_ERROR`）

因此最终改为 Nginx 同时服务前端和 API，前后端同源，彻底避免跨域和协议问题。

> ✅ **绑定域名 + HTTPS 后**，可以重新考虑 Vercel 方案：前端部署到 Vercel + 后端 HTTPS API 直连。

### Q7: docker compose 提示 `version` 属性过时警告

新版 Docker Compose 不再需要 `version: "3.9"`。可删除 docker-compose.yml 第一行，或忽略警告（不影响运行）。

---

*最后更新：2026-04-09*
