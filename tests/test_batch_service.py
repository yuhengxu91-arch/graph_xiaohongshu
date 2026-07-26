import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.batch_task import BatchTask, BatchTaskItem
from app.services.image_fallback_service import GenerationOutcome, ImageModelRef
from app.services.batch_service import BatchService, _tasks, poster_service


class BatchFallbackModelTests(unittest.TestCase):
    def test_batch_models_declare_fallback_tracking_fields(self):
        self.assertTrue(hasattr(BatchTask, "access_token_hash"))
        self.assertTrue(hasattr(BatchTaskItem, "degraded"))
        self.assertTrue(hasattr(BatchTaskItem, "requested_model_name"))
        self.assertTrue(hasattr(BatchTaskItem, "actual_model_name"))
        self.assertTrue(hasattr(BatchTaskItem, "fallback_attempts"))


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

    async def test_removed_provider_uses_system_default_for_single_background_task(self):
        from app.api.v1 import batch as batch_api

        values = iter(["jimeng", None])

        async def execute(statement):
            return SimpleNamespace(scalar_one_or_none=lambda: next(values))

        db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
        create_task = AsyncMock(return_value={
            "success": True,
            "task_id": "task-1",
            "total_count": 1,
        })
        background_tasks = SimpleNamespace(add_task=MagicMock())

        with patch.object(batch_api.brand_service, "get_brand_kit", AsyncMock(return_value=None)):
            with patch.object(
                batch_api.image_model_service,
                "get_default_config",
                AsyncMock(return_value=None),
            ):
                with patch.object(
                    batch_api.batch_service,
                    "create_single_generation_task",
                    create_task,
                ):
                    response = await batch_api.single_custom_generate(
                        batch_api.SingleCustomRequest(prompt="测试"),
                        background_tasks,
                        current_user=SimpleNamespace(id=uuid4()),
                        db=db,
                    )

        self.assertTrue(response.success, response.error)
        model_ref = ImageModelRef.from_dict(
            create_task.await_args.kwargs["shared_config"]["model_ref"]
        )
        self.assertEqual(model_ref.provider, batch_api.poster_service.provider)

    async def test_removed_provider_uses_system_default_for_template_batch(self):
        from app.api.v1 import batch as batch_api
        from app.services import template_service as template_service_module

        values = iter(["jimeng", None])

        async def execute(statement):
            return SimpleNamespace(scalar_one_or_none=lambda: next(values))

        db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
        template_id = uuid4()
        template = SimpleNamespace(
            id=template_id,
            name="喜报",
            style_tag=None,
            config={"default_aspect_ratio": "3:4"},
        )

        with patch.object(
            template_service_module.template_service,
            "get_template",
            AsyncMock(return_value=template),
        ):
            with patch.object(batch_api.brand_service, "get_brand_kit", AsyncMock(return_value=None)):
                with patch.object(
                    batch_api.image_model_service,
                    "get_default_config",
                    AsyncMock(return_value=None),
                ):
                    shared_config = await batch_api._template_shared_config(
                        batch_api.TemplateBatchGenerateRequest(
                            template_id=str(template_id),
                            items=[batch_api.TemplateBatchItemInput(params={"title": "A"})],
                        ),
                        db,
                        SimpleNamespace(id=uuid4()),
                    )

        model_ref = ImageModelRef.from_dict(shared_config["model_ref"])
        self.assertEqual(model_ref.provider, batch_api.poster_service.provider)

    async def test_created_task_persists_only_safe_model_reference(self):
        service = BatchService()
        service._persist_task_create = AsyncMock()
        config_id = uuid4()

        result = await service.create_batch_task(
            [{"title": "A"}],
            {
                "mode": "custom",
                "model_ref": ImageModelRef(
                    source="config",
                    display_name="公共模型",
                    config_id=config_id,
                ).to_dict(),
                "image_model_config": {
                    "api_key": "secret-value",
                    "base_url": "https://secret.example.test",
                },
            },
        )

        shared_config = _tasks[result["task_id"]]["shared_config"]
        serialized = json.dumps(shared_config)
        self.assertNotIn("image_model_config", shared_config)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("base_url", serialized)
        self.assertNotIn("secret-value", serialized)

    async def test_safe_model_ref_is_passed_to_fallback_generation(self):
        service = BatchService()
        service._persist_task_create = AsyncMock()
        service._sync_task_state = AsyncMock()
        service._save_single_output = AsyncMock()
        model_ref = ImageModelRef(
            source="builtin",
            display_name="系统 Gemini",
            provider="gemini",
        )
        generate = AsyncMock(
            return_value={
                "success": True,
                "image_url": "/static/custom.png",
                "prompt_used": "p",
                "degraded": True,
                "requested_model_name": "系统 Gemini",
                "actual_model_name": "备用模型",
                "fallback_attempts": 1,
            }
        )
        result = await service.create_single_generation_task(
            mode="custom",
            params={"prompt": "测试"},
            runtime_input={},
            shared_config={
                "aspect_ratio": "3:4",
                "model_ref": model_ref.to_dict(),
            },
        )

        with patch(
            "app.services.batch_service.poster_service.generate_custom",
            generate,
        ):
            await service.run_single_generation_task(result["task_id"])

        self.assertEqual(generate.await_count, 1)
        self.assertEqual(generate.await_args.kwargs["primary_model_ref"], model_ref)
        status = service.get_batch_status(result["task_id"])
        self.assertEqual(status["degraded_count"], 1)
        self.assertEqual(status["items"][0]["actual_model_name"], "备用模型")

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

    async def test_single_custom_generation_keeps_images_out_of_persistence(self):
        service = BatchService()
        service._persist_task_create = AsyncMock()
        service._sync_task_state = AsyncMock()
        service._save_single_output = AsyncMock()

        captured = {}

        async def fake_generate_custom(**kwargs):
            captured.update(kwargs)
            return {"success": True, "image_url": "/static/custom.png", "prompt_used": "p"}

        result = await service.create_single_generation_task(
            mode="custom",
            params={"prompt": "一张春日海报"},
            runtime_input={"reference_images": [{"image_base64": "AAAA", "name": "图1"}]},
            shared_config={"aspect_ratio": "3:4", "style_tags": ["清新"]},
        )

        # 大体积输入只在内存，不进入持久化的 item_params
        persisted_item = _tasks[result["task_id"]]["items"][0]["item_params"]
        self.assertNotIn("reference_images", persisted_item)
        self.assertNotIn("image_base64", persisted_item)

        with patch(
            "app.services.batch_service.poster_service.generate_custom",
            AsyncMock(side_effect=fake_generate_custom),
        ):
            await service.run_single_generation_task(result["task_id"])

        self.assertEqual(captured["reference_images"], [{"image_base64": "AAAA", "name": "图1"}])
        self.assertEqual(captured["aspect_ratio"], "3:4")
        status = service.get_batch_status(result["task_id"])
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["total_count"], 1)
        self.assertEqual(status["items"][0]["image_url"], "/static/custom.png")

    async def test_single_edit_generation_failure_is_reported(self):
        service = BatchService()
        service._persist_task_create = AsyncMock()
        service._sync_task_state = AsyncMock()
        service._save_single_output = AsyncMock()

        async def fake_generate_edit(**kwargs):
            return {"success": False, "error": "第三方 503"}

        result = await service.create_single_generation_task(
            mode="edit",
            params={"edit_prompt": "换成夜景"},
            runtime_input={"image_base64": "AAAA"},
            shared_config={"aspect_ratio": "9:16"},
        )

        with patch(
            "app.services.batch_service.poster_service.generate_edit",
            AsyncMock(side_effect=fake_generate_edit),
        ):
            await service.run_single_generation_task(result["task_id"])

        status = service.get_batch_status(result["task_id"])
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["items"][0]["error_message"], "图片生成失败，请重试")

    async def test_local_save_failure_does_not_repeat_provider_generation(self):
        service = BatchService()
        service._persist_task_create = AsyncMock()
        service._sync_task_state = AsyncMock()
        service._save_batch_output = AsyncMock()
        model_ref = ImageModelRef(
            source="builtin",
            display_name="系统 Gemini",
            provider="gemini",
        )
        generate = AsyncMock(
            return_value=GenerationOutcome(
                image_base64="AAAA",
                degraded=False,
                requested_model_name="系统 Gemini",
                actual_model_name="系统 Gemini",
                fallback_attempts=0,
            )
        )
        result = await service.create_batch_task(
            [{"prompt": "测试"}],
            {
                "mode": "custom",
                "aspect_ratio": "3:4",
                "model_ref": model_ref.to_dict(),
            },
        )

        with patch.object(
            poster_service,
            "generate_image_with_fallback",
            generate,
        ):
            with patch.object(
                poster_service,
                "_save_image",
                MagicMock(side_effect=OSError("disk path leaked")),
            ):
                await service.run_batch_task(result["task_id"])

        self.assertEqual(generate.await_count, 1)
        status = service.get_batch_status(result["task_id"])
        self.assertEqual(status["status"], "failed")
        self.assertEqual(
            status["items"][0]["error_message"],
            "图片生成失败，请重试",
        )

    async def test_retry_restarts_from_original_model_ref(self):
        service = BatchService()
        service._persist_task_create = AsyncMock()
        service._sync_task_state = AsyncMock()
        service._save_single_output = AsyncMock()
        model_ref = ImageModelRef(
            source="builtin",
            display_name="系统 Gemini",
            provider="gemini",
        )
        generate = AsyncMock(
            side_effect=[
                {"success": False, "error": "temporary"},
                {
                    "success": True,
                    "image_url": "/static/retry.png",
                    "prompt_used": "p",
                    "degraded": False,
                    "requested_model_name": "系统 Gemini",
                    "actual_model_name": "系统 Gemini",
                    "fallback_attempts": 0,
                },
            ]
        )
        result = await service.create_single_generation_task(
            mode="custom",
            params={"prompt": "测试"},
            runtime_input={},
            shared_config={
                "aspect_ratio": "3:4",
                "model_ref": model_ref.to_dict(),
            },
        )

        with patch(
            "app.services.batch_service.poster_service.generate_custom",
            generate,
        ):
            await service.run_single_generation_task(result["task_id"])
            await service.retry_failed_items(result["task_id"])

        self.assertEqual(generate.await_count, 2)
        for call in generate.await_args_list:
            self.assertEqual(call.kwargs["primary_model_ref"], model_ref)
        status = service.get_batch_status(result["task_id"])
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["items"][0]["fallback_attempts"], 0)

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
