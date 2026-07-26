# 图片生成自动降级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 当主图片供应商出现临时故障时，按管理员指定顺序自动切换备用公共模型，正常返回图片并向用户显示安全的降级提示。

**Architecture:** 使用安全的 `ImageModelRef` 替代任务中的完整运行时配置；新增 `ImageGenerationError` 统一供应商错误语义，并由 `ImageFallbackService` 负责实时查询候选、能力过滤和顺序尝试。现有 `PosterService` 保留提示词构造与图片保存职责，批任务持久化每项的降级元数据，前端分别提供管理员配置和结果提示。

**Tech Stack:** FastAPI、SQLAlchemy AsyncIO、PostgreSQL JSON、httpx、Pydantic、Vue 3、Node test runner、pytest。

---

## 文件结构

- Create: `app/services/image_generation_errors.py`：统一错误类型和三类供应商错误分类。
- Create: `app/services/image_fallback_service.py`：安全模型引用、候选解析、能力匹配和顺序降级。
- Create: `tests/test_image_generation_errors.py`：错误码、HTTP 状态、审核和下载错误分类。
- Create: `tests/test_image_fallback_service.py`：候选排序、能力过滤、降级执行和元数据。
- Create: `tests/test_batch_task_access.py`：任务所有者和匿名访问令牌校验。
- Create: `tests/test_image_fallback_migrations.py`：PostgreSQL 升级 SQL 和历史密钥清理。
- Create: `frontend/tests/imageFallback.test.mjs`：管理员配置和结果提示回归测试。
- Create: `frontend/src/utils/imageFallback.js`：结果汇总和条件展示纯函数。
- Create: `frontend/src/utils/batchTaskAccess.js`：匿名任务令牌持有及请求头构造。
- Modify: `app/models/image_model.py`：备用优先级及能力字段。
- Modify: `app/models/batch_task.py`：访问令牌哈希和子项降级字段。
- Modify: `app/core/db.py`：幂等启动迁移和历史任务密钥清理。
- Modify: `app/services/image_model_service.py`：备用候选、能力校验、安全模型引用和序列化。
- Modify: `app/services/profile_service.py`：返回安全模型引用，不再把 Key 放进任务配置。
- Modify: `app/services/poster_service.py`：供应商适配器抛结构化错误，生成阶段接入协调器。
- Modify: `app/services/batch_service.py`：保存安全引用、降级元数据和安全错误。
- Modify: `app/api/v1/image_model.py`：管理员配置 schema。
- Modify: `app/api/v1/batch.py`：访问令牌、任务鉴权和状态字段。
- Modify: `app/api/v1/poster.py`：同步生成接口传递安全模型引用并返回降级字段。
- Modify: `frontend/src/components/profile/PreferenceForm.vue`：备用顺序和能力设置。
- Modify: `frontend/src/components/poster/ResultDisplay.vue`：单图提示、逐项标记和批量汇总。
- Modify: `frontend/src/components/poster/PanelTemplate.vue`：模板队列的逐项标记和汇总。
- Modify: `frontend/src/api.js`：任务访问令牌和 fetch SSE。

### Task 1: 数据模型与幂等迁移

**Files:**
- Modify: `app/models/image_model.py`
- Modify: `app/models/batch_task.py`
- Modify: `app/core/db.py`
- Modify: `app/services/image_model_service.py`
- Test: `tests/test_image_model_config.py`
- Test: `tests/test_batch_service.py`

- [ ] **Step 1: 写失败测试**

断言模型具备：

```python
assert hasattr(ImageModelConfig, "fallback_enabled")
assert hasattr(ImageModelConfig, "fallback_priority")
assert hasattr(ImageModelConfig, "capabilities")
assert hasattr(BatchTaskItem, "degraded")
assert hasattr(BatchTaskItem, "requested_model_name")
assert hasattr(BatchTaskItem, "actual_model_name")
assert hasattr(BatchTaskItem, "fallback_attempts")
assert hasattr(BatchTask, "access_token_hash")
```

并测试 `ImageModelService` 拒绝启用备用但没有正优先级的配置，序列化包含能力字段但不暴露真实 Key。

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest tests/test_image_model_config.py tests/test_batch_service.py -q`

Expected: FAIL，缺少新字段或校验。

- [ ] **Step 3: 实现最小模型与迁移**

新增字段（包括 `batch_tasks.access_token_hash`）并在 `init_db()` 中执行 `ADD COLUMN IF NOT EXISTS`。历史 `batch_tasks.shared_config` 是 PostgreSQL JSON，不是 JSONB，清理 SQL 必须显式转换：

```sql
UPDATE batch_tasks
SET shared_config = (
    shared_config::jsonb
    #- '{image_model_config,api_key}'
    #- '{image_model_config,base_url}'
)::json
WHERE shared_config::jsonb #> '{image_model_config}' IS NOT NULL
```

把 PostgreSQL 升级语句提取为可测试的 `_postgres_upgrade_statements()`。`tests/test_image_fallback_migrations.py` 包含两层验证：

1. 使用 PostgreSQL dialect 编译并通过 fake connection 执行全部语句，断言包含 `::jsonb`、`::json`、令牌列和全部降级列。
2. 使用项目测试 PostgreSQL 开启事务，插入包含 `image_model_config.api_key/base_url`、其他模型字段及其他 `shared_config` 键的任务行，执行升级语句后查询，断言只删除敏感路径；再执行一次证明幂等。覆盖空对象和缺失路径，最后回滚事务。

真实 PostgreSQL 集成测试是发布门槛，不允许用 SQLite 跳过后声称迁移已验证。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONPATH=. pytest tests/test_image_model_config.py tests/test_batch_service.py tests/test_image_fallback_migrations.py -q`

- [ ] **Step 5: 提交**

```bash
git add app/models app/core/db.py app/services/image_model_service.py tests
git commit -m "feat(models): add image fallback configuration"
```

### Task 2: 安全模型引用与候选解析

**Files:**
- Create: `app/services/image_fallback_service.py`
- Modify: `app/services/image_model_service.py`
- Modify: `app/services/profile_service.py`
- Modify: `app/services/batch_service.py`
- Modify: `app/api/v1/batch.py`
- Modify: `app/api/v1/poster.py`
- Test: `tests/test_image_fallback_service.py`
- Test: `tests/test_profile_service.py`
- Test: `tests/test_poster_service.py`
- Test: `tests/test_batch_service.py`

- [ ] **Step 1: 写失败测试**

覆盖：

- 公共模型、内置模型和系统默认解析为安全引用。
- 引用不含 `api_key`、`base_url`。
- 候选实时查询，排除主模型，按 `fallback_priority/sort_order/created_at` 排序。
- 停用、删除、能力不匹配的模型被跳过。

目标接口：

```python
@dataclass(frozen=True)
class ImageModelRef:
    source: Literal["builtin", "config"]
    display_name: str
    provider: str | None = None
    config_id: UUID | None = None

async def resolve_runtime_config(db, model_ref) -> dict:
    ...
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest tests/test_image_fallback_service.py tests/test_profile_service.py tests/test_poster_service.py tests/test_batch_service.py -q`

- [ ] **Step 3: 实现安全引用**

API 层和任务 `shared_config` 只保存 `model_ref` 的字典。先实现“只解析并调用主模型”的兼容路径：后台执行时通过独立 session 将引用解析成短生命周期 runtime config，再调用现有 `PosterService`，本任务暂不启用备用链。内置模型从环境变量解析。切换持久化格式后，现有单张和批量生成测试必须保持全绿。

同步 `app/api/v1/poster.py` 路径在调用 `PosterService` 前通过请求数据库会话解析安全引用，不把 `ImageModelRef` 误传为 runtime config。增加公共模型、内置模型和系统默认三种同步 API 回归测试，本提交仍只调用主模型、不启用降级。

- [ ] **Step 4: 增加密钥不落库测试**

创建任务后递归检查 `shared_config`：

```python
serialized = json.dumps(shared_config)
assert "api_key" not in serialized
assert "base_url" not in serialized
assert "secret-value" not in serialized
```

- [ ] **Step 5: 运行测试并提交**

Run: `PYTHONPATH=. pytest tests/test_image_fallback_service.py tests/test_profile_service.py tests/test_poster_service.py tests/test_batch_service.py -q`

```bash
git add app/services app/api tests
git commit -m "refactor(images): persist safe model references"
```

### Task 3: 供应商结构化错误分类

**Files:**
- Create: `app/services/image_generation_errors.py`
- Modify: `app/services/poster_service.py`
- Test: `tests/test_image_generation_errors.py`
- Test: `tests/test_poster_service.py`

- [ ] **Step 1: 写错误分类失败测试**

覆盖 OpenAI、Gemini、豆包：

- 连接失败、超时、临时 429、500/502/503/504 可降级。
- 501/505/507、401/403、参数错误、余额/长期配额、审核拒绝不可降级。
- 错误码比较对大小写、下划线和短横线归一化。
- 余额、配额和审核业务码/关键词优先于 HTTP 429。
- HTTP 200 根级 `error` 走错误表。
- HTTP 200、无业务错误、无审核信号且无图片数据时抛 retryable 空结果错误。
- Gemini `finishReason=STOP` 且无审核信号、无图片时允许降级。
- 无法识别的业务错误默认 `retryable=false`。
- Gemini `promptFeedback.blockReason`、`safetyRatings`、`SAFETY/PROHIBITED_CONTENT/BLOCKLIST/SPII/IMAGE_SAFETY` 不得当作空图片。
- 豆包根级 `error`、`data.error`、`item.error` 按规格优先级解析。
- `CancelledError` 原样传播。
- 图片下载 404/408/429/500/502/503/504、非图片、超出大小上限和解码失败可降级。
- 图片下载 400/401/403 及其他明确 4xx 不降级。
- 内联 Base64 无效或无法解码按无效供应商结果分类。

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest tests/test_image_generation_errors.py -q`

- [ ] **Step 3: 实现错误类型和纯分类函数**

```python
class ImageGenerationError(RuntimeError):
    def __init__(self, category, safe_message, *, retryable=False,
                 provider_status=None, internal_code=None):
        ...
```

分类函数只接收状态码和经过长度限制的结构化错误字段，不记录响应体。

- [ ] **Step 4: 改造供应商适配器**

适配器成功返回有效 Base64；失败抛 `ImageGenerationError`。清除本功能涉及的三个供应商调用链中的全部 `print`，包括成功路径 URL、模型地址、提示词片段和错误响应；不得记录 URL/Base URL 或提示词。统一改用脱敏结构化 logger。`CancelledError` 不捕获。

测试同时捕获 logger 和 stdout/stderr，分别覆盖成功、失败、候选跳过路径，断言无 Key、Base URL、完整响应体和提示词片段。

- [ ] **Step 5: 运行测试并提交**

Run: `PYTHONPATH=. pytest tests/test_image_generation_errors.py tests/test_poster_service.py -q`

```bash
git add app/services/image_generation_errors.py app/services/poster_service.py tests
git commit -m "feat(images): classify provider failures"
```

### Task 4: 顺序降级协调器

**Files:**
- Modify: `app/services/image_fallback_service.py`
- Modify: `app/services/poster_service.py`
- Test: `tests/test_image_fallback_service.py`

- [ ] **Step 1: 写协调器失败测试**

使用可控 fake adapter 验证：

- 主模型成功时不查询/调用备用模型。
- 主模型临时失败后依次尝试候选。
- 非 retryable 错误立即终止。
- `derive_required_capabilities()` 根据调用输入推导并测试：
  - 无参考图：`text_to_image`
  - 单参考图：`single_reference`
  - 多参考图：`multiple_references`
  - 普通改图、风格迁移、扩图和尺寸适配：`image_edit`
  - 局部重绘和擦除：`image_edit + mask_edit`
  - 所有模式检查 `aspect_ratios`
- 自定义多参考图、模板图片槽、edit、inpaint、erase、style transfer、outpaint、adapt 和 `export_all` 的能力组合均有测试。
- 能力不匹配候选被跳过。
- `aspect_ratios=[]` 表示允许供应商自行适配，不能视为不支持全部比例。
- 能力字段缺失或包含未知能力时，候选默认不参与对应降级。
- 备用成功返回：

```python
GenerationOutcome(
    image_base64="...",
    degraded=True,
    requested_model_name="主模型",
    actual_model_name="备用模型",
    fallback_attempts=1,
)
```

- 所有候选失败时抛最后一个安全错误。
- 取消发生后不再调用候选。

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest tests/test_image_fallback_service.py -q`

- [ ] **Step 3: 实现协调器**

每次主模型出现 retryable 错误后才查询当前候选。每个候选执行前重新确认启用状态和能力。协调器接收 `GenerationContext(chain_id, task_id, item_id, user_id)`；结构化日志记录这些关联字段、模型 ID、分类、状态、耗时、尝试次数和最终状态。

测试使用日志捕获器和递归响应检查，断言日志、数据库任务、状态响应、SSE 和重试响应中不存在 API Key、Base URL、完整第三方响应体或完整提示词。

- [ ] **Step 4: 运行测试并提交**

Run: `PYTHONPATH=. pytest tests/test_image_fallback_service.py tests/test_poster_service.py -q`

```bash
git add app/services/image_fallback_service.py app/services/poster_service.py tests
git commit -m "feat(images): add ordered provider fallback"
```

### Task 5: 后台任务集成与安全状态

**Files:**
- Modify: `app/models/batch_task.py`
- Modify: `app/services/batch_service.py`
- Modify: `app/api/v1/batch.py`
- Modify: `app/api/v1/poster.py`
- Test: `tests/test_batch_service.py`
- Test: `tests/test_batch_retry_api.py`

- [ ] **Step 1: 写失败测试**

覆盖自定义、模板、普通批量、单/多参考图、改图、局部重绘、擦除、风格迁移、扩图、尺寸适配和 `export_all`：

- 成功项保存四个降级字段。
- 混合批量正确统计降级项。
- `error_message` 只保存固定安全文案，不保存内部异常。
- 本地 `_save_image`、品牌叠加和作品库失败不触发备用模型。
- 重试从原主模型引用开始，并重新查询当前候选。

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest tests/test_batch_service.py tests/test_batch_retry_api.py -q`

- [ ] **Step 3: 集成结果元数据**

`GenerationOutcome` 在保存图片前拆出 Base64 和降级字段；批任务同步到 DB 和状态 DTO。同步接口返回同一组字段。

- [ ] **Step 4: 运行测试并提交**

Run: `PYTHONPATH=. pytest tests/test_batch_service.py tests/test_batch_retry_api.py tests/test_poster_service.py -q`

```bash
git add app/models/batch_task.py app/services/batch_service.py app/api tests
git commit -m "feat(images): persist fallback generation status"
```

### Task 6: 任务访问控制与匿名令牌

**Files:**
- Modify: `app/models/batch_task.py`
- Modify: `app/core/db.py`
- Modify: `app/services/batch_service.py`
- Modify: `app/api/v1/batch.py`
- Modify: `frontend/src/api.js`
- Create: `frontend/src/utils/batchTaskAccess.js`
- Modify: `frontend/src/components/poster/ResultDisplay.vue`
- Modify: `frontend/src/components/poster/PanelTemplate.vue`
- Create: `tests/test_batch_task_access.py`
- Test: `frontend/tests/imageFallback.test.mjs`

- [ ] **Step 1: 写访问控制失败测试**

覆盖：

- 登录任务仅所有者或管理员可状态查询、SSE、追加、重试和下载。
- 匿名任务必须提供正确令牌。
- 登录用户不能仅凭 UUID 访问匿名任务。
- 数据库和内存只保存 SHA-256 令牌哈希。
- 使用 `secrets.token_urlsafe(32)` 生成令牌；不同任务令牌不重复且满足最低长度。
- 管理员无需匿名令牌即可访问匿名任务的状态、SSE、追加、重试和下载接口。
- 创建响应只返回一次明文令牌；前端任务上下文 `{ taskId, accessToken }` 只保存在当前组件内存，不写 localStorage/sessionStorage。
- 状态轮询、模板追加、重试和 fetch 下载均从同一任务上下文构造 `X-Task-Access-Token`。
- SSE helper 使用 fetch stream 和请求头；现有 UI 继续使用轮询，不创建未使用的 SSE 连接。

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest tests/test_batch_task_access.py -q`

- [ ] **Step 3: 实现统一校验**

创建任务返回一次性 `task_access_token`。`batchTaskAccess.js` 提供可执行纯函数：

```js
createBatchTaskContext(response)
batchTaskHeaders(context)
```

`api.js` 中 `getBatchStatus`、`appendTemplateBatchItems`、`retryBatchTask`、`downloadBatchTask` 和 `streamBatchStatus` 都接收任务上下文而不是裸 `taskId`。下载改为带请求头的 fetch/blob。`ResultDisplay` 和 `PanelTemplate` 在当前任务生命周期内持有上下文并传给全部 helper。

`app/core/db.py` 为现有数据库幂等增加 `access_token_hash` 列；Task 1 已覆盖首次迁移，本任务补充真实创建、校验和前端传递。

- [ ] **Step 4: 运行测试并提交**

Run:

```bash
PYTHONPATH=. pytest tests/test_batch_task_access.py tests/test_batch_retry_api.py -q
node --test frontend/tests/imageFallback.test.mjs
```

```bash
git add app frontend/src/api.js tests
git commit -m "fix(batch): enforce task ownership"
```

### Task 7: 管理员备用模型 UI

**Files:**
- Modify: `app/api/v1/image_model.py`
- Modify: `app/services/image_model_service.py`
- Modify: `frontend/src/components/profile/PreferenceForm.vue`
- Modify: `frontend/src/api.js`
- Create: `frontend/tests/imageFallback.test.mjs`

- [ ] **Step 1: 写前后端失败测试**

后端验证只有管理员可写备用配置、优先级必须为正整数、能力只接受白名单字段。新增模型按 `provider_type` 获得保守默认能力并有单元测试。把表单 payload 归一化提取为可执行纯函数，测试开关关闭时清空优先级、能力白名单和支持比例；组件再保留一条入口接线回归测试。

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
PYTHONPATH=. pytest tests/test_image_model_config.py -q
node --test frontend/tests/imageFallback.test.mjs
```

- [ ] **Step 3: 实现 API 和弹窗控件**

在现有新增/编辑模型弹窗中增加备用开关、数字输入及能力复选框；列表显示备用序号。非管理员沿用现有隐藏逻辑。

- [ ] **Step 4: 运行测试并提交**

```bash
PYTHONPATH=. pytest tests/test_image_model_config.py -q
node --test frontend/tests/imageFallback.test.mjs
git add app/api app/services frontend tests
git commit -m "feat(admin): configure fallback image models"
```

### Task 8: 结果降级提示

**Files:**
- Create: `frontend/src/utils/imageFallback.js`
- Modify: `frontend/src/components/poster/ResultDisplay.vue`
- Modify: `frontend/src/components/poster/PanelTemplate.vue`
- Modify: `frontend/tests/imageFallback.test.mjs`

- [ ] **Step 1: 写失败测试**

验证：

- 正常成功不显示提示。
- 单张降级显示固定提示和主/实际模型。
- 批量卡片逐项显示“备用模型”标记。
- 批量顶部显示降级数量汇总。
- 模板批量独立结果网格显示同样的逐项标记和顶部汇总。
- 全部失败仍显示重试按钮。
- `imageFallback.js` 的 `fallbackNotice(item)`、`countDegradedItems(items)` 用真实输入做可执行测试，证明 `degraded=false` 时不生成提示且汇总数量正确。

- [ ] **Step 2: 运行测试确认失败**

Run: `node --test frontend/tests/imageFallback.test.mjs`

- [ ] **Step 3: 实现 UI**

使用非阻断的琥珀色状态条，文案固定为：

> 当前图片由备用模型生成，效果可能与所选模型不同。如有问题，请联系管理员查看原因。

- [ ] **Step 4: 运行测试并提交**

```bash
node --test frontend/tests/imageFallback.test.mjs
git add frontend
git commit -m "feat(images): show fallback generation notice"
```

### Task 9: 全量验证与部署说明

**Files:**
- Modify: `README.md`
- Modify: `DEPLOYMENT.md`

- [ ] **Step 1: 更新部署说明**

说明启动迁移、新字段默认不会启用任何备用模型、管理员配置步骤、单 worker 与服务重启边界。

- [ ] **Step 2: 运行后端全量测试**

Run: `PYTHONPATH=. pytest tests -q`

Expected: 全部通过，仅保留既有弃用警告。

- [ ] **Step 3: 运行前端全量测试**

Run: `node --test frontend/tests/*.test.mjs`

- [ ] **Step 4: 运行生产构建和静态检查**

```bash
cd frontend
npm run build -- --outDir /private/tmp/graph-xiaohongshu-fallback-final --emptyOutDir
cd ..
python -m py_compile app/services/image_generation_errors.py app/services/image_fallback_service.py
git diff --check
```

- [ ] **Step 5: 最终提交**

```bash
git add README.md DEPLOYMENT.md
git commit -m "docs: document image generation fallback"
```
