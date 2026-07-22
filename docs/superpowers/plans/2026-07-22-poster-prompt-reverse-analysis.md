# Poster Prompt Reverse Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and execute every RED/GREEN checkpoint in order.

**Goal:** 在提示词库提供基于 Doubao-Seed-2.1-Pro 的安全海报逆向分析，并支持确认后收藏或应用到自定义海报生成。

**Architecture:** 后端新增独立分析服务，负责图片净化、用户限流、方舟 Responses API 和结构化结果验证；提示词 API 只负责认证、请求模型和 HTTP 错误映射。前端使用纯工具函数处理图片与状态，弹窗负责上传、分析、编辑、保存和应用，提示词库页面负责入口和列表刷新。

**Tech Stack:** FastAPI、Pydantic、httpx、Pillow、Vue 3、Axios、pytest/unittest、Node test runner

---

### Task 1: 图片净化（逐行为 TDD）

**Files:** Create `app/services/poster_prompt_analyzer.py`, `tests/test_poster_prompt_analyzer.py`; modify `app/core/config.py`

- [ ] RED：分别测试严格 data URL/Base64、14MB 编码上限、10MB 解码上限；运行定向测试，确认因实现缺失失败。
- [ ] GREEN：实现输入解析与体积限制；运行定向测试通过并提交。
- [ ] RED：分别测试 JPG/PNG/WEBP 声明与真实格式一致、多帧拒绝、8192 边长、2400 万像素；确认按预期失败。
- [ ] GREEN：用 Pillow verify/load 实现格式与图像限制；运行定向测试通过并提交。
- [ ] RED：测试透明图白底、RGB WEBP quality=92/method=4、EXIF/文本元数据移除、从不落盘；确认失败。
- [ ] GREEN：实现内存净化转码；运行定向测试通过并提交。
- [ ] RED：测试转码超过 10MB 时逐次缩小 20%，最长边低于 1024 后仍超限则拒绝；确认失败。
- [ ] GREEN：实现循环缩放与终止条件；运行整个图片净化测试通过并提交。

### Task 2: 结构化结果与方舟请求（逐行为 TDD）

**Files:** Modify `app/services/poster_prompt_analyzer.py`, `tests/test_poster_prompt_analyzer.py`, `app/core/config.py`

- [ ] RED：测试结果全部字段、禁止额外字段、数组/字符串边界、颜色与比例枚举、海报与非海报条件；确认失败。
- [ ] GREEN：实现 `PosterAnalysisResult` 及条件校验；运行定向测试通过并提交。
- [ ] RED：精确断言 `/responses` payload：抗图片指令注入系统提示词、完整 JSON Schema、`additionalProperties:false`、全部 required、`store:false`、关闭 thinking、无 tools；确认失败。
- [ ] GREEN：加入四个 ARK 配置项并构造官方 Responses 请求；运行定向测试通过并提交。
- [ ] RED：分别测试顶层 `output_text`、`output[].content[].text`、拒答/审核、空输出、截断、非 JSON、错误 Schema；确认失败。
- [ ] GREEN：实现安全提取、JSON 解析与 Pydantic 校验；运行定向测试通过并提交。
- [ ] RED：分别测试 401/403、429、安全 Retry-After、超时、连接错误、5xx、其他 4xx；断言仅连接错误和 5xx 重试一次。
- [ ] GREEN：实现稳定错误分类和重试；日志测试断言只含内部 request ID/类别/状态，不含 Key、图片、提示词或上游正文；运行定向测试通过并提交。

### Task 3: 单实例用户限流（逐行为 TDD）

**Files:** Modify `app/services/poster_prompt_analyzer.py`, `tests/test_poster_prompt_analyzer.py`

- [ ] RED：用可注入时钟测试同用户并发拒绝、不同用户互不影响、十次/小时滑动窗口和安全 Retry-After。
- [ ] GREEN：使用异步锁保护共享状态，实现进程内 per-user limiter。
- [ ] RED：测试成功、业务异常、取消任务均释放并发占用，并发拒绝不计入次数。
- [ ] GREEN：用 `try/finally` 完成清理；运行服务测试全量通过并提交。

### Task 4: 认证 API 与错误映射（逐行为 TDD）

**Files:** Modify `app/api/v1/prompt.py`; create `tests/test_prompt_reverse_analysis_api.py`

- [ ] RED：测试 `ReverseAnalyzeRequest` 对空值、类型错误、超过 14MB 返回 422，无认证返回 401，静态路由不会匹配 `/{prompt_id}`。
- [ ] GREEN：在所有动态 prompt ID 路由前加入认证 `POST /prompts/reverse-analyze` 和请求模型。
- [ ] RED：参数化测试所有服务错误到 `{detail:{code,message}}`、状态码与安全 `Retry-After` 的映射。
- [ ] GREEN：实现错误映射；使用假分析器确认 user ID 与图片传递，不访问真实方舟；运行 API 和服务测试通过并提交。

### Task 5: 前端图片工具与弹窗状态（逐行为 TDD）

**Files:** Create `frontend/src/utils/posterReverseAnalysis.js`, `frontend/src/components/prompt/PosterPromptAnalyzerModal.vue`, `frontend/tests/promptReverseAnalysis.test.mjs`; modify `frontend/src/api.js`

- [ ] RED：Node 行为测试 MIME/10MB、4096 缩放尺寸、14MB data URL、高质量 WEBP 和安全错误解析；确认失败。
- [ ] GREEN：实现可测试纯函数和 `reverseAnalyzePrompt`；仅最长边超 4096 时缩放，不复用 1600/0.82 组件。
- [ ] RED：测试 idle/analyzing/success/not_poster/error/saving/saved 转换、请求序号、过期/关闭后响应忽略、重新分析清除 saved。
- [ ] GREEN：实现弹窗状态控制；运行状态测试通过。
- [ ] RED：源码契约测试遮罩和 Escape 不关闭、唯一 X 入口、未保存内容确认、分析中关闭、隐私提示、OCR 插值且无 `v-html`、复制功能。
- [ ] GREEN：实现上传、分析、结构化结果和可编辑提示词 UI；运行前端定向测试通过并提交。

### Task 6: 保存与分类应用（逐行为 TDD）

**Files:** Modify `frontend/src/components/prompt/PosterPromptAnalyzerModal.vue`, `frontend/src/PromptLibraryPage.vue`, `frontend/tests/promptReverseAnalysis.test.mjs`

- [ ] RED：测试保存前 trim 后 1..4000；标题、poster 分类、去重最多 5 标签、`source_mode:reverse_analysis`、成功锁定、失败保留和重复保存拦截。
- [ ] GREEN：复用 `createPrompt` 实现确认保存；成功发出刷新事件。
- [ ] RED：测试应用前校验、`reverse-analysis:` 临时 ID、分类自动进入 poster/custom、sessionStorage/导航失败清理、不调用 `/use`。
- [ ] GREEN：复用 `savePromptApplyPayload` 实现应用并集成顶部入口；运行定向测试通过并提交。
- [ ] RED/GREEN：错误只读取允许的 `detail.code/message` 和规范化 Retry-After，未知结构显示固定文案。

### Task 7: 运维说明、回归与提交

**Files:** Modify `README.md`（或现有部署文档）及上述实现文件

- [ ] 记录 `ARK_API_KEY`、`ARK_VISION_MODEL`、`ARK_BASE_URL`、`ARK_VISION_TIMEOUT` 的无密钥示例；注明当前限流仅适用于单 backend，扩容前需迁移 Redis。
- [ ] 运行 `PYTHONPATH=. pytest tests/test_poster_prompt_analyzer.py -q`。
- [ ] 运行 `PYTHONPATH=. pytest tests/test_prompt_reverse_analysis_api.py -q`。
- [ ] 运行 `PYTHONPATH=. pytest tests -q`，确认所有 HTTP 测试均是假客户端。
- [ ] 运行 `node --test frontend/tests/promptReverseAnalysis.test.mjs` 和 `node --test frontend/tests/*.test.mjs`。
- [ ] 在 `frontend` 运行 `npm run build -- --outDir /private/tmp/graph-xiaohongshu-frontend-dist --emptyOutDir`。
- [ ] 运行 `git diff --check`、`git status --short`，审查文件范围和敏感信息，提交功能实现。
