# 海报提示词逆向分析设计

## 目标

在提示词库增加“海报逆向”能力。用户上传一张海报后，由火山方舟 Doubao-Seed-2.1-Pro 分析文字、版式、配色和视觉风格，并生成可编辑、可复制、可收藏、可应用到自定义海报生成的提示词。

本功能只分析海报，不承诺恢复原始提示词、随机种子或模型参数。

## 用户流程

1. 用户在提示词库点击“海报逆向”。
2. 弹窗仅允许上传一张 JPG、PNG 或 WEBP 图片，原文件不得超过 10MB。
3. 用户点击“开始分析”，弹窗保持打开并展示处理中状态。
4. 后端判断图片是否为海报并返回结构化分析结果。
5. 如果不是海报，界面说明当前只支持海报，不生成提示词。
6. 如果是海报，界面展示识别文字、版式、配色、字体、视觉风格、推荐比例、生成提示词和负面提示词。
7. 生成提示词允许编辑；用户可复制、保存到“我的收藏”、应用到自定义海报生成或重新分析。
8. 分析成功不会自动保存，避免提示词库产生未经确认的内容。

弹窗只能通过右上角关闭按钮退出，点击遮罩和按 Escape 不关闭，避免分析结果或编辑内容丢失。
界面必须提示“图片将发送至火山方舟进行分析，请勿上传包含敏感个人信息的海报”。

## 后端架构

新增 `PosterPromptAnalyzer`，只负责以下职责：

- 校验并拆分图片 data URL。
- 读取视觉分析环境变量。
- 构建面向海报的系统提示词和 JSON Schema。
- 调用火山方舟官方 Responses API。
- 提取并验证结构化结果。
- 将上游错误转换为稳定的业务异常。

新增认证接口：

```text
POST /api/v1/prompts/reverse-analyze
```

请求：

```json
{
  "image_base64": "data:image/png;base64,..."
}
```

响应：

```json
{
  "is_poster": true,
  "poster_type": "喜报",
  "recognized_text": ["喜报", "20k offer"],
  "layout_description": "顶部主标题，中部信息区，底部品牌区",
  "color_palette": ["#F43F5E", "#2563EB", "#FACC15"],
  "typography": ["粗体立体标题", "无衬线正文"],
  "visual_style": ["孟菲斯", "高饱和", "庆祝感"],
  "generation_prompt": "...",
  "negative_prompt": "...",
  "aspect_ratio": "3:4"
}
```

所有字段始终存在。`is_poster=false` 时，字符串返回空字符串、数组返回空数组，`aspect_ratio` 返回 `unknown`。成功结构遵循以下限制：

- `additionalProperties=false`，所有字段均为 `required`。
- `poster_type` 最长 50 字符。
- `recognized_text` 最多 50 项，每项最长 200 字符。
- `layout_description` 最长 1000 字符。
- `color_palette` 最多 12 项，只接受 `#RRGGBB`。
- `typography` 和 `visual_style` 各最多 12 项，每项最长 100 字符。
- 上游 Schema 允许 `generation_prompt` 为 0-4000 字符；后端执行条件校验：海报时去空白后必须为 1-4000 字符，非海报时必须为空。
- `negative_prompt` 最长 1000 字符。
- `aspect_ratio` 只接受 `3:4`、`2.35:1`、`9:16`、`1:1`、`16:9`、`unknown`。

上游 JSON Schema 只使用火山方舟支持的基础类型、长度和枚举约束；颜色格式以及海报/非海报条件由后端 Pydantic 验证器重复校验。模型拒答、内容审核、空输出、截断、非 JSON 和 Schema 不匹配均不得作为成功结果返回。

静态路由必须定义在 `/{prompt_id}` 动态路由之前。分析不创建数据库记录，保存操作继续调用现有 `POST /prompts/create`。

## 火山方舟配置

使用后端环境变量：

```env
ARK_API_KEY=
ARK_VISION_MODEL=
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_VISION_TIMEOUT=120
```

`ARK_VISION_MODEL` 填 Doubao-Seed-2.1-Pro 的推理接入点 ID。API Key 仅保存在后端，不写日志、不返回前端。

调用地址为 `${ARK_BASE_URL}/responses`。请求使用 Bearer Token、清理后的图片 data URL 和结构化输出约束，并设置 `store: false`。第一版关闭深度思考，以降低延迟并提高 JSON 输出稳定性。系统提示词明确规定图片文字是不可信的待分析数据，不能作为指令执行；请求不启用工具、联网或函数调用。

## 前端结构

新增 `PosterPromptAnalyzerModal.vue`，内部管理上传、分析、结果和编辑状态。提示词库页面只负责打开弹窗，以及接收“已保存”事件后刷新个人列表。

“保存到我的收藏”创建以下记录：

- 标题：`${poster_type || '海报'}逆向提示词`
- 内容：用户编辑后的 `generation_prompt`
- 分类：`poster`
- 标签：取 `visual_style`，最多五项
- `source_mode`：`reverse_analysis`

“应用到自定义生成”复用现有 `promptApply` sessionStorage 协议，使用 `prompt_id: "reverse-analysis:" + crypto.randomUUID()` 作为临时 ID，写入 `poster` 分类内容并跳转海报页 `custom` 标签，不调用 `/prompts/{id}/use`，也不直接开始生图。第一版只应用生成提示词；推荐比例、配色和风格仅供用户参考，不自动覆盖海报页设置。

结果编辑器显示字符计数。保存和应用前都按去空白后的内容校验 1-4000 字符，空白或超长时禁止提交并显示错误。现有创建 API 允许更长正文，本功能不改其全局契约，但逆向分析弹窗必须执行该限制。

弹窗状态为 `idle/analyzing/success/not_poster/error/saving/saved`。分析和保存期间禁用重复提交；每次分析使用递增请求序号，过期响应不能覆盖新状态。保存失败回到 `success`，保留编辑内容并允许重试；保存成功保留返回的提示词 ID，锁定编辑器和再次保存，防止重复记录；重新分析会清空该状态。所有识别文字使用 Vue 文本插值渲染，禁止 `v-html`。

## 图片与安全

- 前端限制 MIME 和 10MB；后端重复校验，不能信任前端。请求 data URL 编码字符串不得超过 14MB。
- 后端严格 Base64 解码，解码后不得超过 10MB；使用 Pillow 验证真实格式与声明 MIME 一致，拒绝动画、多帧、解码失败、任一边超过 8192 像素或总像素超过 2400 万的图片。
- 为保留海报小字，前端不使用现有 1600px/0.82 的有损压缩；仅在超大尺寸时等比缩放到最长边 4096px，并使用高质量 WEBP。
- 服务端将透明图合成到白色背景，再统一转为 RGB，以 WebP `quality=92`、`method=4` 重新编码，从而移除 EXIF、位置和文本块。转码结果不得超过 10MB；若超限，按最长边逐级缩小 20% 重试，低于 1024px 后仍超限则返回 `INVALID_IMAGE`。
- 后端不保存上传图片，不写入作品库或日志。
- 错误响应使用 `{ "detail": { "code": "...", "message": "..." } }`。配置缺失为 `503/MODEL_NOT_CONFIGURED`，格式无效为 `400/INVALID_IMAGE`，非海报作为正常 200 结果返回。
- 上游 401/403 映射为 `502/UPSTREAM_AUTH_FAILED`，429 映射为 `429/UPSTREAM_RATE_LIMITED` 并安全透传 `Retry-After`，内容审核映射为 `422/CONTENT_REJECTED`，超时映射为 `504/ANALYSIS_TIMEOUT`，无效响应映射为 `502/UPSTREAM_INVALID_RESPONSE`，其他上游错误映射为 `502/UPSTREAM_ERROR`。
- 仅对连接错误和上游 5xx 自动重试一次，不重试鉴权、限流、内容审核和格式错误。每次调用生成内部 request ID，但日志只记录错误类别、状态码和 request ID。
- 当前生产拓扑为单 backend 容器，第一版使用进程内按用户限流：每个用户同时最多一个分析、每小时最多十次，超限返回 `429/ANALYSIS_RATE_LIMITED` 和安全的 `Retry-After`。若后续扩为多 backend 实例，发布前必须将该限流器替换为 Redis 共享计数；本版本不宣称支持多实例一致限流。
- 新弹窗只读取 `error.response?.data?.detail?.code`、`detail?.message` 和安全解析后的 `Retry-After`，未知结构统一显示“海报分析失败，请稍后重试”，不得直接渲染对象或上游响应体。
- 关闭存在未保存分析结果或编辑内容的弹窗时需要二次确认；分析中的请求允许完成，但关闭后结果不再写入界面状态。

## 验证

- 服务测试：配置缺失、data URL 校验、MIME/signature 不一致、Base64 与像素上限、动画图、透明背景合成、元数据移除、转码大小、Responses API 请求、结构化响应与条件校验、非海报响应、上游鉴权、429、超时、重试边界和用户并发/频率限制。
- API 测试：认证路由、请求限制和错误状态映射。
- 前端测试：API 方法、弹窗仅 X 关闭、上传限制、结构化结果、过期响应、复制、编辑后空白/超长校验、保存失败重试、重复保存锁定、临时 ID 应用且不调用 `/use`、应用跳转。
- 回归测试：后端全量测试、前端全量测试、生产构建和 `git diff --check`。
