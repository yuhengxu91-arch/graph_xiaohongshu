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

调用地址为 `${ARK_BASE_URL}/responses`。请求使用 Bearer Token、图片 data URL 和结构化输出约束。第一版关闭深度思考，以降低延迟并提高 JSON 输出稳定性。

## 前端结构

新增 `PosterPromptAnalyzerModal.vue`，内部管理上传、分析、结果和编辑状态。提示词库页面只负责打开弹窗，以及接收“已保存”事件后刷新个人列表。

“保存到我的收藏”创建以下记录：

- 标题：`${poster_type || '海报'}逆向提示词`
- 内容：用户编辑后的 `generation_prompt`
- 分类：`poster`
- 标签：取 `visual_style`，最多五项
- 来源：`reverse_analysis`

“应用到自定义生成”复用现有 `promptApply` sessionStorage 协议，写入 `poster` 分类内容并跳转海报页 `custom` 标签，不直接开始生图。

## 图片与安全

- 前端限制 MIME 和 10MB；后端重复校验，不能信任前端。
- 为保留海报小字，前端不使用现有 1600px/0.82 的有损压缩；仅在超大尺寸时等比缩放到最长边 4096px，并使用较高质量 WEBP。
- 后端不保存上传图片，不写入作品库或日志。
- 上游 401/403 映射为“视觉模型鉴权失败”；超时映射为“海报分析超时”；其他上游错误不向用户暴露响应体或密钥。
- 配置缺失返回 503，格式无效返回 400，上游失败返回 502/504。

## 验证

- 服务测试：配置缺失、data URL 校验、Responses API 请求、结构化响应解析、非海报响应、上游鉴权和超时。
- API 测试：认证路由、请求限制和错误状态映射。
- 前端测试：API 方法、弹窗仅 X 关闭、上传限制、结构化结果、复制、保存和应用跳转。
- 回归测试：后端全量测试、前端全量测试、生产构建和 `git diff --check`。
