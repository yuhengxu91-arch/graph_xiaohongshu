import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.services.batch_service import BatchService, _tasks


class BatchServiceTemplateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _tasks.clear()

    async def asyncTearDown(self):
        _tasks.clear()

    async def test_template_batch_runs_items_sequentially(self):
        service = BatchService()
        service._persist_task_create = AsyncMock()
        service._sync_task_state = AsyncMock()
        service._save_batch_output = AsyncMock()

        active = 0
        max_active = 0

        async def fake_generate_from_db_template(**kwargs):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return {
                "success": True,
                "image_url": f"/static/{kwargs['params']['title']}.png",
                "prompt_used": kwargs["params"]["title"],
            }

        result = await service.create_batch_task(
            [{"title": "A"}, {"title": "B"}, {"title": "C"}],
            {
                "mode": "template",
                "sequential": True,
                "template_config": {"ai_prompt_template": "{title}"},
                "template_name": "喜报",
                "template_style_tag": None,
                "aspect_ratio": "3:4",
            },
        )

        with patch(
            "app.services.batch_service.poster_service.generate_from_db_template",
            AsyncMock(side_effect=fake_generate_from_db_template),
        ):
            await service.run_batch_task(result["task_id"])

        self.assertEqual(max_active, 1)
        status = service.get_batch_status(result["task_id"])
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["success_count"], 3)

    async def test_append_batch_items_adds_pending_items(self):
        service = BatchService()
        service._persist_task_create = AsyncMock()
        service._persist_new_items = AsyncMock()
        service._sync_task_state = AsyncMock()

        result = await service.create_batch_task(
            [{"title": "A"}],
            {
                "mode": "template",
                "sequential": True,
                "template_config": {"ai_prompt_template": "{title}"},
                "template_name": "喜报",
            },
        )

        append_result = await service.append_batch_items(
            result["task_id"],
            [{"title": "B"}],
        )

        self.assertEqual(append_result["total_count"], 2)
        self.assertEqual(append_result["appended_count"], 1)
        status = service.get_batch_status(result["task_id"])
        self.assertEqual(status["items"][1]["title"], "B")
        self.assertEqual(status["items"][1]["status"], "pending")

    async def test_append_during_running_template_batch_runs_next(self):
        service = BatchService()
        service._persist_task_create = AsyncMock()
        service._persist_new_items = AsyncMock()
        service._sync_task_state = AsyncMock()
        service._save_batch_output = AsyncMock()

        started = asyncio.Event()
        calls = []
        active = 0
        max_active = 0

        async def fake_generate_from_db_template(**kwargs):
            nonlocal active, max_active
            calls.append(kwargs["params"]["title"])
            active += 1
            max_active = max(max_active, active)
            started.set()
            await asyncio.sleep(0.05)
            active -= 1
            return {
                "success": True,
                "image_url": f"/static/{kwargs['params']['title']}.png",
                "prompt_used": kwargs["params"]["title"],
            }

        result = await service.create_batch_task(
            [{"title": "A"}],
            {
                "mode": "template",
                "sequential": True,
                "template_config": {"ai_prompt_template": "{title}"},
                "template_name": "喜报",
            },
        )

        with patch(
            "app.services.batch_service.poster_service.generate_from_db_template",
            AsyncMock(side_effect=fake_generate_from_db_template),
        ):
            runner = asyncio.create_task(service.run_batch_task(result["task_id"]))
            await started.wait()
            await service.append_batch_items(result["task_id"], [{"title": "B"}])
            await runner

        self.assertEqual(calls, ["A", "B"])
        self.assertEqual(max_active, 1)
        status = service.get_batch_status(result["task_id"])
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["success_count"], 2)

    async def test_append_during_template_batch_finalization_is_not_lost(self):
        service = BatchService()
        service._persist_task_create = AsyncMock()
        service._persist_new_items = AsyncMock()
        service._save_batch_output = AsyncMock()

        appended = False
        calls = []

        async def fake_sync_task_state(task, **kwargs):
            nonlocal appended
            if task["status"] == "completed" and task.get("worker_running") and not appended:
                appended = True
                await service.append_batch_items(task["id"], [{"title": "B"}])

        async def fake_generate_from_db_template(**kwargs):
            calls.append(kwargs["params"]["title"])
            await asyncio.sleep(0)
            return {
                "success": True,
                "image_url": f"/static/{kwargs['params']['title']}.png",
                "prompt_used": kwargs["params"]["title"],
            }

        service._sync_task_state = AsyncMock(side_effect=fake_sync_task_state)
        result = await service.create_batch_task(
            [{"title": "A"}],
            {
                "mode": "template",
                "sequential": True,
                "template_config": {"ai_prompt_template": "{title}"},
                "template_name": "喜报",
            },
        )

        with patch(
            "app.services.batch_service.poster_service.generate_from_db_template",
            AsyncMock(side_effect=fake_generate_from_db_template),
        ):
            await service.run_batch_task(result["task_id"])

        self.assertEqual(calls, ["A", "B"])
        status = service.get_batch_status(result["task_id"])
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["success_count"], 2)
