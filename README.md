# 🚀 AI 内容运营助手

基于 **LangGraph 1.0+** / **FastAPI** / **Vue 3** / **Remotion** 构建的全链路内容创作平台。
涵盖 AI 选题 → 文章撰写 → 配图生成 → **AI 海报生成** → **多平台内容适配** → **AI 视频生成**。

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

### 🎬 AI 视频生成（Phase 6）
| 功能 | 说明 |
|------|------|
| LLM 脚本生成 | 输入选题，**DeepSeek** 自动生成结构化视频脚本（标题 + 要点 + 旁白），支持 Doubao 降级 |
| Tavily 搜索增强 | 自动联网搜索选题相关资料，注入 LLM 提升脚本质量 |
| TTS 语音合成 | 火山引擎 TTS 自动将旁白转为真人级语音 |
| Remotion 渲染 | Node.js 服务端渲染 MP4，支持逐帧动画 |
| 多模板系统 | 内置「干货技能卡」+ 「数据可视化」两套模板，可扩展 |
| 横竖屏适配 | 支持 **16:9** 横屏 和 **9:16** 竖屏，所有场景组件自适应布局 |
| 全流水线编排 | 选题 → 脚本 → TTS → 渲染 → MP4，后台异步执行 |

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | **FastAPI** (Python 3.10+) |
| 包管理 | **uv** (极速 Python 包管理器) |
| 工作流引擎 | **LangGraph 1.0+** |
| 数据库 | **PostgreSQL** + SQLAlchemy (async) |
| AI 图片 | **Gemini API** (generateContent + IMAGE modality) |
| AI 文案 | **DeepSeek** (主力) / 火山引擎 Doubao (降级) |
| AI 搜索 | **Tavily** (联网搜索增强) |
| AI 语音 | **火山引擎 TTS**（语音合成） |
| 视频渲染 | **Remotion** (React → MP4，Node.js 服务) |
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
psql -U postgres -c "CREATE DATABASE langgraph_db;"
```

#### 2. 后端（使用 uv 极速安装）

```bash
# 创建虚拟环境（自动在项目根目录生成 .venv）
uv venv

# 安装所有依赖（通常 < 1 秒）
uv pip install -r requirements.txt

# 激活环境
# Windows
.venv\Scripts\activate
# Linux / Mac
source .venv/bin/activate
```

> 💡 如果尚未安装 `uv`，可通过 `curl -LsSf https://astral.sh/uv/install.sh | sh` 一键安装

#### 3. 配置 `.env`

```env
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/aicontent
POSTGRES_URI=postgresql://postgres:your_password@localhost:5432/aicontent
IMAGE_API_KEY=your_gemini_api_key
IMAGE_API_BASE_URL=https://generativelanguage.googleapis.com
IMAGE_MODEL=gemini-2.0-flash-exp-image-generation

# DeepSeek（视频脚本生成，主力模型）
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# Tavily（联网搜索增强）
TAVILY_API_KEY=your_tavily_api_key

# 火山引擎 TTS（视频语音合成）
TTS_APP_ID=your_tts_app_id
TTS_ACCESS_TOKEN=your_tts_access_token
TTS_VOICE_TYPE=zh_female_cancan_mars

# Remotion 渲染服务
REMOTION_SERVICE_URL=http://localhost:3100
```

#### 4. 启动后端

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 5. 启动 Remotion 渲染服务

```bash
cd video-renderer
npm install
npm run dev          # 启动在 http://localhost:3100
```

#### 6. 启动前端

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
| Remotion 渲染 | http://localhost:3100/health |

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

### AI 视频生成 `/api/v1/video`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/generate` | 创建视频生成任务（后台异步执行） |
| GET | `/status/{task_id}` | 查询任务状态与进度 |
| POST | `/script/preview` | 仅生成脚本预览（不渲染） |
| GET | `/list` | 获取历史视频列表 |
| GET | `/download/{task_id}` | 获取视频下载链接 |

---

## 📁 项目结构

```
graph_xiaohongshu/
├── app/                              # 后端 Python
│   ├── api/v1/
│   │   ├── poster.py                 # 海报生成 API
│   │   ├── batch.py                  # 批量生成 API（含 SSE）
│   │   ├── platform.py               # 多平台适配 API
│   │   ├── video.py                  # AI 视频生成 API
│   │   ├── workflow.py               # 内容工作流 API
│   │   ├── auth.py                   # 认证 API
│   │   └── image.py                  # 通用图片 API
│   ├── data/
│   │   └── platform_rules.py         # 5 大平台规则配置
│   ├── services/
│   │   ├── poster_service.py         # 海报生成核心逻辑
│   │   ├── batch_service.py          # 批量 & 系列一致性逻辑
│   │   ├── platform_adapter_service.py # 多平台文案改写服务
│   │   ├── video_service.py          # 视频生成编排（脚本→TTS→渲染）
│   │   ├── video_script_service.py   # LLM 视频脚本生成（DeepSeek + Tavily）
│   │   ├── tavily_service.py         # Tavily 联网搜索服务
│   │   ├── tts_service.py            # 火山引擎 TTS 语音合成
│   │   ├── llm_service.py            # LLM 服务封装
│   │   └── image_service.py          # 图片生成服务
│   ├── graph/                        # LangGraph 工作流
│   ├── models/                       # SQLAlchemy ORM（含 video_task.py）
│   ├── core/                         # 配置 & 数据库
│   └── main.py                       # FastAPI 入口
│
├── video-renderer/                   # Remotion 视频渲染服务
│   ├── src/
│   │   ├── compositions/
│   │   │   ├── KnowledgeVideo/       # 「干货技能卡」模板
│   │   │   │   ├── index.tsx          # 主 Composition
│   │   │   │   ├── TitleScene.tsx     # 开场标题场景（横竖屏自适应）
│   │   │   │   ├── ContentScene.tsx   # 内容展示场景（横竖屏自适应）
│   │   │   │   └── OutroScene.tsx     # 结尾 CTA 场景（横竖屏自适应）
│   │   │   └── DataVizVideo/         # 「数据可视化」模板
│   │   │       ├── index.tsx          # 主 Composition
│   │   │       ├── NumberFlipScene.tsx # 数字翻转动画场景
│   │   │       ├── BarChartScene.tsx  # 柱状图动画场景
│   │   │       └── DataCardScene.tsx  # 数据卡片场景
│   │   ├── server.ts                 # Express HTTP 渲染服务
│   │   ├── render-video.ts           # Remotion 渲染封装
│   │   ├── templates.ts              # 模板注册表
│   │   └── Root.tsx                  # Remotion 入口
│   └── package.json
│
├── frontend/                         # 前端 Vue 3
│   └── src/
│       ├── App.vue                   # 路由壳组件
│       ├── MainApp.vue               # 主应用页面
│       ├── WorkflowPage.vue          # 内容工作流主页
│       ├── PosterPage.vue            # 海报生成主页
│       ├── PlatformPage.vue          # 多平台适配主页
│       ├── BrandPage.vue             # 品牌包设置页
│       ├── components/               # 各模块子组件
│       ├── router.js                 # Vue Router 路由配置
│       └── api.js                    # API 客户端
│
├── static/
│   ├── videos/                       # 生成的 MP4 视频
│   └── audio/                        # 生成的 TTS 音频
├── start.bat                         # 一键启动（Windows）
├── stop.bat                          # 一键停止（Windows）
├── requirements.txt
├── FEATURE.md                        # 视频效果优化 Feature 列表
├── feature_creative_ideas.md         # 功能创意扩展方案
├── .env
└── README.md
```

---

## ⚠️ 注意事项

1. **数据库**: 确保 PostgreSQL 运行且可访问
2. **Gemini API Key**: 在 `.env` 中配置 `IMAGE_API_KEY`
3. **图片存储**: 生成的海报保存在 `static/images/posters/`，需确保目录可写
4. **并发控制**: 批量生成使用 `Semaphore(3)` 限流；全平台导出使用 `Semaphore(2)` 限流
5. **视频渲染**: 需先启动 Remotion 服务 (`cd video-renderer && npm run dev`)，渲染期间约需 30-60 秒
6. **TTS 配置**: 火山引擎 TTS 需在控制台开通语音合成服务并获取 APP_ID 和 Access Token

## 📄 License

MIT
