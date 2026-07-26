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
- Create: `frontend/tests/imageFallback.test.mjs`：管理员配置和结果提示回归测试。
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
```

并测试 `ImageModelService` 拒绝启用备用但没有正优先级的配置，序列化包含能力字段但不暴露真实 Key。

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest tests/test_image_model_config.py tests/test_batch_service.py -q`

Expected: FAIL，缺少新字段或校验。

- [ ] **Step 3: 实现最小模型与迁移**

新增字段并在 `init_db()` 中执行 `ADD COLUMN IF NOT EXISTS`。历史 `batch_tasks.shared_config` 使用 PostgreSQL JSONB 更新删除：

```sql
shared_config #- '{image_model_config,api_key}'
              #- '{image_model_config,base_url}'
```

迁移必须先判断 PostgreSQL 方言；测试环境不支持 JSONB 时跳过清理 SQL。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONPATH=. pytest tests/test_image_model_config.py tests/test_batch_service.py -q`

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
- Modify: `app/api/v1/batch.py`
- Modify: `app/api/v1/poster.py`
- Test: `tests/test_image_fallback_service.py`
- Test: `tests/test_profile_service.py`
- Test: `tests/test_poster_service.py`

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

Run: `PYTHONPATH=. pytest tests/test_image_fallback_service.py tests/test_profile_service.py tests/test_poster_service.py -q`

- [ ] **Step 3: 实现安全引用**

API 层和任务 `shared_config` 只保存 `model_ref` 的字典。协调器执行时用独立 session 查询公共模型 Key；内置模型从环境变量解析。

- [ ] **Step 4: 增加密钥不落库测试**

创建任务后递归检查 `shared_config`：

```python
serialized = json.dumps(shared_config)
assert "api_key" not in serialized
assert "base_url" not in serialized
assert "secret-value" not in serialized
```

- [ ] **Step 5: 运行测试并提交**

Run: `PYTHONPATH=. pytest tests/test_image_fallback_service.py tests/test_profile_service.py tests/test_poster_service.py -q`

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
- HTTP 200 根级 `error` 走错误表。
- Gemini `SAFETY` 不得当作空图片。
- `CancelledError` 原样传播。
- 图片下载 404/408/429/500/502/503/504、非图片和解码失败可降级。

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

适配器成功返回有效 Base64；失败抛 `ImageGenerationError`。移除错误路径中的 `print(response.text)`，改用脱敏 logger。`CancelledError` 不捕获。

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
- 能力不匹配候选被跳过。
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

每次主模型出现 retryable 错误后才查询当前候选。每个候选执行前重新确认启用状态和能力。日志只记录模型 ID、分类、状态和耗时。

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

覆盖自定义、模板、普通批量和改图任务：

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
- Modify: `app/services/batch_service.py`
- Modify: `app/api/v1/batch.py`
- Modify: `frontend/src/api.js`
- Create: `tests/test_batch_task_access.py`

- [ ] **Step 1: 写访问控制失败测试**

覆盖：

- 登录任务仅所有者或管理员可状态查询、SSE、追加、重试和下载。
- 匿名任务必须提供正确令牌。
- 登录用户不能仅凭 UUID 访问匿名任务。
- 数据库和内存只保存 SHA-256 令牌哈希。

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest tests/test_batch_task_access.py -q`

- [ ] **Step 3: 实现统一校验**

创建任务返回一次性 `task_access_token`。普通请求使用 `X-Task-Access-Token`；SSE 前端改用 `fetch` + `ReadableStream`，同样通过请求头提交令牌。

- [ ] **Step 4: 运行测试并提交**

Run: `PYTHONPATH=. pytest tests/test_batch_task_access.py tests/test_batch_retry_api.py -q`

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

后端验证只有管理员可写备用配置、优先级必须为正整数、能力只接受白名单字段。前端静态回归测试验证开关、优先级、能力控件及 payload。

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
- Modify: `frontend/src/components/poster/ResultDisplay.vue`
- Modify: `frontend/tests/imageFallback.test.mjs`

- [ ] **Step 1: 写失败测试**

验证：

- 正常成功不显示提示。
- 单张降级显示固定提示和主/实际模型。
- 批量卡片逐项显示“备用模型”标记。
- 批量顶部显示降级数量汇总。
- 全部失败仍显示重试按钮。

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
