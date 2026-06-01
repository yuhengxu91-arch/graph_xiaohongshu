# Requirements Document

## Introduction

为作品库（Gallery）中的图片提供重命名功能。用户可以在图片详情页修改作品名称，系统通过专用的 `PATCH /gallery/{work_id}/rename` 端点处理重命名请求，并对名称进行校验（长度限制、空白处理）。该功能复用现有的 `poster_generations.title` 字段，无需数据库迁移。

## Glossary

- **Gallery_Service**：作品库服务层，负责作品的增删改查业务逻辑
- **API_Router**：FastAPI 路由层，负责接收 HTTP 请求、参数校验和响应返回
- **作品（Work）**：存储在 `poster_generations` 表中的一条记录，代表用户生成的图片作品
- **所有者（Owner）**：创建该作品的用户，通过 `user_id` 字段标识
- **标题（Title）**：作品的名称字段，存储在 `poster_generations.title` 中，最大 200 字符

## Requirements

### 需求 1：重命名作品

**用户故事：** 作为一个用户，我希望能够重命名我的作品，以便更好地组织和识别我的图片。

#### 验收标准

1. WHEN 用户提交一个去除首尾空白后长度为 1 至 200 个字符的新标题，THE Gallery_Service SHALL 将作品标题更新为去除首尾空白后的新标题
2. WHEN 重命名成功，THE API_Router SHALL 返回 HTTP 200 响应，包含作品 ID、更新后的标题和更新时间
3. WHEN 重命名成功，THE Gallery_Service SHALL 更新作品的 `updated_at` 时间戳为当前时间
4. IF 提交的新标题去除首尾空白后为空字符串或超过 200 个字符，THEN THE API_Router SHALL 返回 HTTP 422 响应，包含指明标题长度不符合要求的错误信息
5. IF 指定的作品 ID 不存在或不属于当前用户，THEN THE API_Router SHALL 返回 HTTP 404 响应，包含指明作品不存在的错误信息

### 需求 2：标题输入校验

**用户故事：** 作为一个用户，我希望系统对标题输入进行合理校验，以便我不会意外设置无效的作品名称。

#### 验收标准

1. WHEN 用户提交的标题去除首尾空白后长度为 0 THEN API_Router SHALL 拒绝该请求并返回 HTTP 422 响应
2. WHEN 用户提交的标题超过 200 个字符 THEN API_Router SHALL 返回 HTTP 422 校验错误，响应体包含指明长度超限的错误信息
3. WHEN 用户提交的标题包含首尾空白 THEN Gallery_Service SHALL 自动去除首尾空白后再保存
4. THE Gallery_Service SHALL 将清理后的标题截断至最多 200 个字符后保存

### 需求 3：权限控制

**用户故事：** 作为一个用户，我希望只有我自己能重命名我的作品，以便我的作品不会被他人篡改。

#### 验收标准

1. IF 已认证用户尝试重命名不属于自己的作品，THEN API_Router SHALL 返回 HTTP 404 响应，响应体包含错误信息指示作品不存在
2. IF 已认证用户尝试重命名不存在的作品，THEN API_Router SHALL 返回 HTTP 404 响应，响应体包含错误信息指示作品不存在
3. THE API_Router SHALL 对不存在的作品和无权访问的作品返回相同的 HTTP 状态码（404）和相同的响应体结构及错误描述文本，使调用方无法通过响应差异判断作品是否存在
4. IF 未携带有效 JWT 令牌的请求尝试重命名任何作品，THEN API_Router SHALL 返回 HTTP 401 响应，不执行任何修改操作

### 需求 4：数据完整性

**用户故事：** 作为一个用户，我希望重命名操作只修改标题，不影响作品的其他信息。

#### 验收标准

1. WHEN 重命名操作执行后 THEN Gallery_Service SHALL 仅修改该作品的 title 和 updated_at 字段，其余字段（tags、image_url、mode、prompt、style_tags、params、is_favorite、created_at 等）的值与操作前完全一致
2. WHEN 对同一作品连续执行 2 次或以上相同标题的重命名操作 THEN Gallery_Service SHALL 每次均返回相同的 title 值，且除 updated_at 外的其他字段值与首次操作前一致
3. IF 重命名操作指定的作品不存在或不属于当前用户 THEN Gallery_Service SHALL 返回 None，且不修改任何数据库记录

### 需求 5：API 端点设计

**用户故事：** 作为一个开发者，我希望有一个语义清晰的专用重命名端点，以便前端调用时意图明确。

#### 验收标准

1. THE API_Router SHALL 提供 `PATCH /api/v1/gallery/{work_id}/rename` 端点用于重命名操作，其中 `work_id` 为 UUID 格式，成功时返回 HTTP 200 及更新后的作品详情
2. THE API_Router SHALL 要求请求体包含 `new_title` 字段，类型为字符串，长度为 1 至 200 个字符（含首尾）
3. IF 请求未携带有效的 Bearer Token，THEN THE API_Router SHALL 返回 HTTP 401 响应
4. IF `work_id` 对应的作品不存在或不属于当前认证用户，THEN THE API_Router SHALL 返回 HTTP 404 响应
5. IF `new_title` 为空字符串或超过 200 个字符，THEN THE API_Router SHALL 返回 HTTP 422 响应并包含指明验证失败原因的错误信息

### 需求 6：前端交互

**用户故事：** 作为一个用户，我希望在图片详情页能够方便地编辑作品名称，以便快速完成重命名。

#### 验收标准

1. WHEN 用户点击名称区域 THEN 前端 SHALL 切换为内联编辑模式，显示输入框并预填当前名称，输入框最大允许输入 200 个字符
2. WHEN 用户在编辑模式下按下回车键或点击确认按钮 THEN 前端 SHALL 禁用输入框和确认按钮以防止重复提交，并调用重命名 API
3. WHEN 用户按下 Escape 键或点击输入框外部区域 THEN 前端 SHALL 取消编辑并恢复原始名称显示
4. WHEN 重命名 API 返回成功 THEN 前端 SHALL 退出编辑模式并立即更新页面上显示的作品名称为新值
5. IF 用户提交的名称为空或仅包含空白字符 THEN 前端 SHALL 阻止提交并在输入框附近显示错误提示信息，指明名称不能为空
6. IF 重命名 API 返回失败（网络错误或服务端错误）THEN 前端 SHALL 恢复输入框为可编辑状态、保留用户已输入的内容，并显示错误提示信息指明操作失败
