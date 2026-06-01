# Implementation Plan: Gallery Image Rename

## Overview

为作品库添加专用的重命名 API 端点（`PATCH /gallery/{work_id}/rename`），复用现有 `PosterGeneration.title` 字段，无需数据库迁移。实现包括服务层方法、API 路由、请求/响应模型，以及前端交互逻辑。

## Tasks

- [x] 1. 实现服务层重命名方法
  - [x] 1.1 在 `app/services/gallery_service.py` 中添加 `rename_work` 方法
    - 在 `GalleryService` 类中新增 `rename_work` 异步方法
    - 复用现有 `_get_owned_work` 方法验证作品归属权
    - 实现标题清理逻辑：`strip()` 去除首尾空白，截断至 200 字符
    - 空标题（strip 后长度为 0）返回 None
    - 更新 `work.title` 和 `work.updated_at`，调用 `db.flush()`
    - 返回包含 `id`、`title`、`updated_at` 的字典
    - _Requirements: 1.1, 1.3, 2.3, 2.4, 3.1, 4.1, 4.3_

  - [ ]* 1.2 编写 `rename_work` 方法的单元测试
    - 测试成功重命名路径
    - 测试作品不存在时返回 None
    - 测试非所有者无法重命名
    - 测试标题首尾空白自动去除
    - 测试空标题被拒绝
    - 测试超长标题被截断至 200 字符
    - _Requirements: 1.1, 2.1, 2.3, 2.4, 3.1, 4.1_

  - [ ]* 1.3 编写属性测试：重命名后标题一致性
    - **Property 1: 重命名后标题一致性**
    - 对任意有效标题（strip 后长度 1-200），重命名后作品标题等于 `strip(new_title)[:200]`
    - **Validates: Requirements 1.1, 2.3, 2.4**

  - [ ]* 1.4 编写属性测试：纯空白标题拒绝
    - **Property 2: 纯空白标题拒绝**
    - 对任意仅由空白字符组成的字符串，提交为新标题时系统应拒绝，作品标题保持不变
    - **Validates: Requirements 2.1**

  - [ ]* 1.5 编写属性测试：权限隔离
    - **Property 4: 权限隔离**
    - 对任意属于用户 A 的作品，用户 B 尝试重命名应返回 None，数据库无变更
    - **Validates: Requirements 3.1**

  - [ ]* 1.6 编写属性测试：不影响其他字段
    - **Property 5: 不影响其他字段**
    - 对任意作品和有效标题，重命名后标签、图片 URL、模式等其他字段保持不变
    - **Validates: Requirements 4.1**

  - [ ]* 1.7 编写属性测试：幂等性
    - **Property 6: 幂等性**
    - 对同一作品连续执行两次相同重命名，两次结果的标题完全一致
    - **Validates: Requirements 4.2**

- [x] 2. 实现 API 路由层
  - [x] 2.1 在 `app/api/v1/gallery.py` 中添加请求/响应模型和路由
    - 定义 `RenameWorkRequest` Pydantic 模型，包含 `new_title` 字段（min_length=1, max_length=200）
    - 定义 `RenameWorkResponse` Pydantic 模型，包含 `id`、`title`、`updated_at` 字段
    - 添加 `PATCH /{work_id}/rename` 路由端点
    - 调用 `gallery_service.rename_work` 处理业务逻辑
    - 返回 None 时抛出 HTTP 404 异常，detail 为 "作品不存在或无权修改"
    - _Requirements: 1.2, 1.4, 1.5, 2.1, 2.2, 3.2, 3.3, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 2.2 编写 API 端点的集成测试
    - 测试成功重命名返回 200 + 正确响应体
    - 测试作品不存在返回 404
    - 测试非所有者返回 404（与不存在相同响应）
    - 测试空标题返回 422
    - 测试超长标题返回 422
    - 测试未认证请求返回 401
    - 测试与现有 `PUT /gallery/{work_id}` 接口的兼容性
    - _Requirements: 1.2, 1.4, 1.5, 2.1, 2.2, 3.2, 3.3, 3.4, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 2.3 编写属性测试：超长标题拒绝
    - **Property 3: 超长标题拒绝**
    - 对任意长度超过 200 字符的字符串，API 层应返回 HTTP 422 校验错误
    - **Validates: Requirements 2.2**

- [x] 3. 检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [x] 4. 前端交互实现
  - [x] 4.1 在图片详情页组件中实现内联编辑功能
    - 在名称区域添加编辑图标/按钮
    - 点击后切换为内联输入框，预填当前名称
    - 输入框设置 maxlength=200
    - 支持回车键确认提交
    - 支持 Escape 键取消编辑，恢复原始名称
    - 点击输入框外部区域取消编辑
    - 提交时禁用输入框和确认按钮防止重复提交
    - 空标题或纯空白时阻止提交并显示错误提示
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [x] 4.2 实现重命名 API 调用和状态更新
    - 调用 `PATCH /api/v1/gallery/{work_id}/rename` 接口
    - 成功后退出编辑模式，更新页面显示的作品名称
    - 失败时恢复输入框为可编辑状态，保留用户输入内容，显示错误提示
    - _Requirements: 6.2, 6.4, 6.6_

  - [ ]* 4.3 编写前端组件的单元测试
    - 测试编辑模式切换
    - 测试回车确认和 Escape 取消
    - 测试空标题阻止提交
    - 测试 API 调用成功后状态更新
    - 测试 API 调用失败后错误处理
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 5. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

## Notes

- 标记 `*` 的任务为可选任务，可跳过以加快 MVP 交付
- 每个任务引用了具体的需求编号以确保可追溯性
- 检查点确保增量验证
- 属性测试验证通用正确性属性（使用 hypothesis 库）
- 单元测试验证具体示例和边界情况
- 前端实现依赖后端 API 完成后进行

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3"] },
    { "id": 3, "tasks": ["4.1"] },
    { "id": 4, "tasks": ["4.2"] },
    { "id": 5, "tasks": ["4.3"] }
  ]
}
```
