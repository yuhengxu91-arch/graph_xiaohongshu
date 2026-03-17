# 🚀 AI 内容运营助手

基于 **LangGraph 1.0+** / **FastAPI** / **Vue 3** 构建的全链路内容创作平台。
涵盖 AI 选题 → 文章撰写 → 配图生成 → **AI 海报生成** → **多平台内容适配**。

---

## ✨ 功能全景

### 📝 内容工作流（Phase 0）
| 功能 | 说明 |
|------|------|
| AI 选题生成 | 根据主题方向自动生成候选选题，支持结构化展现 |
| AI 文章撰写 | 根据选定选题生成长文草稿，支持流式输出 |
| 沉浸式 UI | **新版设计**：单列居中布局，配备浮动“状态胶囊”切换器 |
| 抽屉控制台 | **新版设计**：一键滑出深色控制台，集成聚合后的执行日志与节点性能指标 |
| 状态持久化 | PostgreSQL + LangGraph Checkpointer |

### 🎨 AI 海报生成（Phase 1 – Phase 4）

#### Phase 1 · 基础生成
| 模式 | 说明 |
|------|------|
| 🎯 自定义生成 | 输入提示词 + 风格标签 + 色调偏好，AI 直出海报 |
| 📋 模板生成 | 选择预置模板、填写文案槽位，AI 基于约束生成 |

#### Phase 2 · 图片编辑
| 模式 | 说明 |
|------|------|
| ✏️ 以图改图 | 上传原图 + 编辑指令，AI 局部修改 |
| 🎭 风格迁移 | 上传原图 + 目标风格标签，支持 light/medium/strong 三档强度 |

#### Phase 3 · 批量与系列
| 模式 | 说明 |
|------|------|
| 📦 批量生成 | 多组提示词并发生成，支持 CSV 导入 |
| 🔗 系列一致性 | 系列模式下首图锚定风格，后续图自动保持一致 |
| 📡 SSE 进度流 | 实时推送批量任务进度 |

#### Phase 4 · 精细化编辑
| 模式 | 说明 |
|------|------|
| 🖌️ 局部重绘 (Inpaint) | Canvas 涂抹遮罩 → AI 定向替换选区内容 |
| 🧹 智能擦除 (Erase) | Canvas 涂抹遮罩 → AI 自动补全背景 |
| 📐 尺寸适配 (Adapt) | 智能裁剪 / AI 扩图 两种策略切换 |
| 📦 全平台导出 (Export All) | 一键并发适配 5 大平台比例 |

### 🌐 多平台内容适配（Phase 5）
| 功能 | 说明 |
|------|------|
| 多平台改写 | 一键将文章改写为小红书 / 抖音 / 微信公众号 / B站 / 微博风格 |
| 平台规则引擎 | 字数限制、图片比例、标签格式、语调风格自动适配 |
| 手机预览模拟 | 实时预览各平台 Feed 流样式（含手机壳 UI） |
| 智能标签推荐 | AI 根据文章内容为每个平台推荐热门标签 |
| 一键复制导出 | 复制文案+标签，快速粘贴到各平台发布 |

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | **FastAPI** (Python 3.10+) |
| 工作流引擎 | **LangGraph 1.0+** |
| 数据库 | **PostgreSQL** + SQLAlchemy (async) |
| AI 图片 | **Gemini API** (generateContent + IMAGE modality) |
| AI 文案 | 火山引擎 Doubao / 通用 LLM |
| 前端框架 | **Vue 3** + Vite |
| 样式 | Vanilla CSS (暗色主题) |

---

## 🚀 快速开始

### ⚡ 一键启动（推荐）

> Windows 下双击项目根目录的 `start.bat`，自动关闭旧进程并启动前后端。

```bash
# 从文件资源管理器双击，或在 CMD 中运行：
start.bat
```

### 手动启动

#### 1. 环境准备

```bash
# 确保 PostgreSQL 运行，创建数据库
psql -U postgres -c "CREATE DATABASE aicontent;"
psql -U postgres -c "CREATE DATABASE langgraph_db;"
```

#### 2. 后端

```bash
python -m venv app/venv

# Windows
call app\venv\Scripts\activate.bat
# Linux / Mac
source app/venv/bin/activate

pip install -r requirements.txt
```

#### 3. 配置 `.env`

```env
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/aicontent
POSTGRES_URI=postgresql://postgres:your_password@localhost:5432/aicontent
IMAGE_API_KEY=your_gemini_api_key
IMAGE_API_BASE_URL=https://generativelanguage.googleapis.com
IMAGE_MODEL=gemini-2.0-flash-exp-image-generation
```

#### 4. 启动后端

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 访问地址

| 入口 | 地址 |
|------|------|
| 前端页面 | http://localhost:3000 |
| API 文档 | http://localhost:8000/docs |

### 一键停止

```bash
# 双击 stop.bat 或在 CMD 中运行：
stop.bat
```

---

## 📡 API 接口总览

### 海报生成 `/api/v1/poster`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/templates` | 获取预置模板列表 |
| GET | `/templates/{index}` | 获取单个模板详情 |
| GET | `/style-tags` | 获取风格标签列表 |
| GET | `/aspect-ratios` | 获取支持的输出尺寸 |
| POST | `/generate/custom` | 自定义生成 |
| POST | `/generate/template` | 模板生成 |
| POST | `/generate/edit` | 以图改图 |
| POST | `/generate/style-transfer` | 风格迁移 |
| POST | `/inpaint` | 局部重绘 |
| POST | `/erase` | 智能擦除 |
| POST | `/adapt` | 单比例尺寸适配 |
| POST | `/export-all` | 全平台一键导出 |

### 批量生成 `/api/v1/poster/batch`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/generate` | 提交批量任务 |
| GET | `/{task_id}/status` | 查询任务状态 |
| GET | `/{task_id}/stream` | SSE 实时进度 |
| GET | `/{task_id}/download` | 下载 ZIP 结果 |
| POST | `/{task_id}/retry` | 重试失败项 |

### 内容工作流 `/api/v1/workflow`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/start` | 启动工作流 |
| GET | `/state/{thread_id}` | 获取工作流状态 |
| POST | `/resume/{thread_id}` | 恢复工作流（选题 / 审核） |

### 多平台适配 `/api/v1/platform`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/rules` | 获取 5 大平台规则配置 |
| POST | `/adapt` | 单平台改写（传入原文+平台 ID） |
| POST | `/adapt-all` | 一键全平台并发改写 |
| GET | `/variants/{thread_id}` | 获取某篇文章的所有平台版本 |
| GET | `/variant/{variant_id}` | 查询单个改写详情 |
| PUT | `/variant/{variant_id}` | 编辑改写版本 |
| DELETE | `/variant/{variant_id}` | 删除改写版本 |

---

## 📁 项目结构

```
graph_xiaohongshu/
├── app/                              # 后端 Python
│   ├── api/v1/
│   │   ├── poster.py                 # 海报生成 API
│   │   ├── batch.py                  # 批量生成 API（含 SSE）
│   │   ├── platform.py               # 多平台适配 API
│   │   ├── workflow.py               # 内容工作流 API
│   │   ├── auth.py                   # 认证 API
│   │   └── image.py                  # 通用图片 API
│   ├── data/
│   │   └── platform_rules.py         # 5 大平台规则配置
│   ├── services/
│   │   ├── poster_service.py         # 海报生成核心逻辑
│   │   ├── batch_service.py          # 批量 & 系列一致性逻辑
│   │   ├── platform_adapter_service.py # 多平台文案改写服务
│   │   ├── llm_service.py            # LLM 服务封装
│   │   └── image_service.py          # 图片生成服务
│   ├── graph/                        # LangGraph 工作流
│   ├── models/                       # SQLAlchemy ORM
│   ├── core/                         # 配置 & 数据库
│   └── main.py                       # FastAPI 入口
│
├── frontend/                         # 前端 Vue 3
│   └── src/
│       ├── App.vue                   # 路由壳组件
│       ├── MainApp.vue               # 主应用页面（基于响应式侧边栏与动态 Flex 布局）
│       ├── WorkflowPage.vue          # 内容工作流主页（沉浸式布局 + 抽屉控制台）
│       ├── PosterPage.vue            # 海报生成主页
│       ├── PlatformPage.vue          # 多平台适配主页
│       ├── BrandPage.vue             # 品牌包设置页
│       ├── components/workflow/      # 工作流子组件（StreamLogPanel 等）
│       ├── components/poster/        # 海报相关子组件（含批量生成优化）
│       ├── components/platform/      # 平台适配子组件
│       │   ├── PlatformTabs.vue      # 平台选项卡
│       │   ├── PlatformPreview.vue   # 手机预览模拟器
│       │   ├── ContentEditor.vue     # 文案编辑器
│       │   └── TagSuggestion.vue     # 标签推荐
│       ├── router.js                 # Vue Router 路由配置
│       └── api.js                    # API 客户端
│
├── start.bat                         # 一键启动（Windows）
├── stop.bat                          # 一键停止（Windows）
├── requirements.txt
├── .env
└── README.md
```

---

## ⚠️ 注意事项

1. **数据库**: 确保 PostgreSQL 运行且可访问
2. **Gemini API Key**: 在 `.env` 中配置 `IMAGE_API_KEY`
3. **图片存储**: 生成的海报保存在 `static/images/posters/`，需确保目录可写
4. **并发控制**: 批量生成使用 `Semaphore(3)` 限流；全平台导出使用 `Semaphore(2)` 限流

## 📄 License

MIT

---

## 数据库迁移（pg_dump）

适用于可停机的逻辑迁移，命令以 Windows PowerShell 为例。

1. A 机器导出
```powershell
New-Item -ItemType Directory -Path C:\temp -Force
pg_dump -F c -h <A_HOST> -U postgres -d langgraph_db -f "C:\temp\langgraph_db.dump"
```

2. 传输到 B 机器（scp / WinSCP / 共享盘任选其一）

3. B 机器建库（已存在可跳过）
```bash
createdb -h <B_HOST> -U postgres langgraph_db
```

4. B 机器导入
```bash
pg_restore -h <B_HOST> -U postgres -d langgraph_db -v /path/to/langgraph_db.dump
```

可选：覆盖已有对象
```bash
pg_restore -h <B_HOST> -U postgres -d langgraph_db --clean --if-exists -v /path/to/langgraph_db.dump
```

注意：
- `pg_dump/pg_restore` 版本尽量与源库一致，目标库版本不低于源库
- 若需迁移角色/权限：`pg_dumpall --globals-only > globals.sql`，再在 B 机器执行 `psql -f globals.sql`