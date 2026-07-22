# Prompt Soft Unpublish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 允许提示词发布者将公开提示词从公共广场软撤回，同时保留个人记录、使用次数和既有复制。

**Architecture:** 在 `PromptService` 增加所有者校验后的公开状态切换，并由独立 API 暴露。前端根据当前用户 ID 控制管理菜单，只让所有者看到撤回入口，确认后调用接口并刷新当前列表。

**Tech Stack:** FastAPI、SQLAlchemy AsyncSession、Vue 3、Axios、Python unittest/pytest、Node test runner

---

### Task 1: 后端软撤回能力

**Files:**
- Create: `tests/test_prompt_unpublish.py`
- Modify: `app/services/prompt_service.py`
- Modify: `app/api/v1/prompt.py`

- [ ] **Step 1: 写失败测试**

覆盖所有者撤回后 `is_public=False` 且内容、使用次数不变；非所有者不能撤回；API 成功返回序列化结果，失败返回 404。

- [ ] **Step 2: 验证测试失败**

Run: `PYTHONPATH=. pytest tests/test_prompt_unpublish.py -q`
Expected: FAIL，提示服务或路由缺少 `unpublish_prompt`。

- [ ] **Step 3: 实现最小后端代码**

在服务中查询记录并校验 `snippet.user_id == user_id`，只修改 `is_public` 和 `updated_at`；新增 `POST /prompts/{prompt_id}/unpublish` 路由。

- [ ] **Step 4: 验证测试通过**

Run: `PYTHONPATH=. pytest tests/test_prompt_unpublish.py -q`
Expected: PASS。

### Task 2: 前端撤回交互

**Files:**
- Modify: `frontend/tests/promptApply.test.mjs`
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/components/prompt/PromptCard.vue`
- Modify: `frontend/src/PromptLibraryPage.vue`

- [ ] **Step 1: 写失败测试**

断言 API 方法、当前用户绑定、所有者菜单、撤回事件、确认文案和处理函数存在。

- [ ] **Step 2: 验证测试失败**

Run: `node --test frontend/tests/promptApply.test.mjs`
Expected: FAIL，缺少撤回 API 与界面绑定。

- [ ] **Step 3: 实现最小前端代码**

加载当前用户 ID，卡片仅向所有者展示菜单；公开记录展示“撤回广场”，确认后调用撤回接口并重新加载列表。

- [ ] **Step 4: 验证测试通过**

Run: `node --test frontend/tests/promptApply.test.mjs`
Expected: PASS。

### Task 3: 回归验证

**Files:**
- Verify only

- [ ] **Step 1: 运行后端测试**

Run: `PYTHONPATH=. pytest tests -q`
Expected: PASS。

- [ ] **Step 2: 运行前端测试与构建**

Run: `node --test frontend/tests/*.test.mjs`
Run: `npm run build -- --outDir /private/tmp/graph-xiaohongshu-frontend-dist --emptyOutDir` from `frontend`
Expected: PASS。

- [ ] **Step 3: 检查变更质量**

Run: `git diff --check && git status --short`
Expected: 无空白错误，仅包含本功能相关文件。
