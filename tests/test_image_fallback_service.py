import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.services.image_fallback_service import ImageModelRef, resolve_runtime_config
from app.services.image_model_service import ImageModelService


class ImageModelRefTests(unittest.TestCase):
    def test_config_reference_round_trips_without_secrets(self):
        config_id = uuid4()
        model_ref = ImageModelRef(
            source="config",
            display_name="公共 GPT Image",
            config_id=config_id,
        )

        payload = model_ref.to_dict()
        restored = ImageModelRef.from_dict(payload)

        self.assertEqual(restored, model_ref)
        serialized = json.dumps(payload)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("base_url", serialized)

    def test_builtin_reference_round_trips_with_provider(self):
        model_ref = ImageModelRef(
            source="builtin",
            display_name="Gemini（系统内置）",
            provider="gemini",
        )

        self.assertEqual(ImageModelRef.from_dict(model_ref.to_dict()), model_ref)

    def test_invalid_reference_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            ImageModelRef(source="config", display_name="缺少配置 ID")
        with self.assertRaises(ValueError):
            ImageModelRef(source="builtin", display_name="缺少 provider")
        with self.assertRaises(ValueError):
            ImageModelRef(
                source="builtin",
                display_name="未知模型",
                provider="unknown",
            )


class RuntimeResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_config_reference_resolves_runtime_secret_only_at_execution(self):
        config_id = uuid4()
        config = SimpleNamespace(
            id=config_id,
            name="公共模型",
            provider_type="openai_image",
            base_url="https://images.example.test",
            model_name="gpt-image-2",
            api_key="secret-value",
            is_active=True,
        )

        with patch(
            "app.services.image_fallback_service.image_model_service.get_config",
            AsyncMock(return_value=config),
        ):
            runtime = await resolve_runtime_config(
                object(),
                ImageModelRef(
                    source="config",
                    display_name="公共模型",
                    config_id=config_id,
                ),
            )

        self.assertIsNone(runtime["provider_override"])
        self.assertEqual(runtime["image_model_config"]["api_key"], "secret-value")
        self.assertEqual(runtime["image_model_config"]["base_url"], "https://images.example.test")

    async def test_builtin_reference_resolves_to_provider_without_database_secret(self):
        runtime = await resolve_runtime_config(
            object(),
            ImageModelRef(
                source="builtin",
                display_name="豆包 Seedream",
                provider="doubao",
            ),
        )

        self.assertEqual(runtime["provider_override"], "doubao")
        self.assertIsNone(runtime["image_model_config"])


class FallbackCandidateTests(unittest.IsolatedAsyncioTestCase):
    async def test_candidates_are_sorted_and_filtered_by_primary_state_and_capability(self):
        service = ImageModelService()
        now = datetime.now(timezone.utc)
        primary_id = uuid4()

        def config(
            name,
            priority,
            sort_order,
            created_offset,
            *,
            active=True,
            fallback=True,
            capabilities=None,
            config_id=None,
        ):
            return SimpleNamespace(
                id=config_id or uuid4(),
                name=name,
                provider_type="openai_image",
                is_active=active,
                fallback_enabled=fallback,
                fallback_priority=priority,
                sort_order=sort_order,
                created_at=now + timedelta(seconds=created_offset),
                capabilities=capabilities
                or {"text_to_image": True, "aspect_ratios": ["3:4"]},
            )

        configs = [
            config("主模型", 1, 0, 0, config_id=primary_id),
            config("停用", 1, 0, 0, active=False),
            config("未加入备用", 1, 0, 0, fallback=False),
            config(
                "能力不匹配",
                1,
                0,
                0,
                capabilities={"text_to_image": False, "aspect_ratios": ["3:4"]},
            ),
            config("备用 B", 2, 0, 20),
            config("备用 A2", 1, 2, 10),
            config("备用 A1", 1, 1, 30),
        ]

        with patch.object(service, "list_configs", AsyncMock(return_value=configs)):
            refs = await service.list_fallback_model_refs(
                object(),
                primary_ref=ImageModelRef(
                    source="config",
                    display_name="主模型",
                    config_id=primary_id,
                ),
                required_capabilities={
                    "text_to_image": True,
                    "aspect_ratio": "3:4",
                },
            )

        self.assertEqual([ref.display_name for ref in refs], ["备用 A1", "备用 A2", "备用 B"])
        self.assertTrue(all(ref.source == "config" for ref in refs))
