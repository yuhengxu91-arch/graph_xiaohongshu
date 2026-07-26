import importlib
import unittest
import uuid

from tests.test_poster_service import FakeAsyncClient, FakeResponse, VALID_IMAGE_B64
from app.models.image_model import ImageModelConfig
from app.services.image_model_service import ImageModelService
from app.services.poster_service import PosterService

poster_service_module = importlib.import_module("app.services.poster_service")


class ImageModelFallbackConfigTests(unittest.TestCase):
    def setUp(self):
        self.service = ImageModelService()

    def test_model_declares_fallback_configuration_fields(self):
        self.assertTrue(hasattr(ImageModelConfig, "fallback_enabled"))
        self.assertTrue(hasattr(ImageModelConfig, "fallback_priority"))
        self.assertTrue(hasattr(ImageModelConfig, "capabilities"))

    def test_enabled_fallback_requires_positive_priority(self):
        config = ImageModelConfig(
            name="备用模型",
            provider_type="openai_image",
            base_url="https://images.example.test",
            model_name="image-model",
            api_key="test-secret-value",
            fallback_enabled=True,
            fallback_priority=0,
            capabilities={"text_to_image": True, "aspect_ratios": []},
        )

        with self.assertRaisesRegex(ValueError, "降级优先级"):
            self.service._validate_config(config)

    def test_safe_serialization_includes_fallback_capabilities_without_real_key(self):
        config = ImageModelConfig(
            id=uuid.uuid4(),
            name="备用模型",
            provider_type="openai_image",
            base_url="https://images.example.test",
            model_name="image-model",
            api_key="test-secret-value",
            fallback_enabled=True,
            fallback_priority=2,
            capabilities={
                "text_to_image": True,
                "single_reference": False,
                "aspect_ratios": ["1:1", "3:4"],
            },
        )

        serialized = self.service.serialize(config)

        self.assertTrue(serialized["fallback_enabled"])
        self.assertEqual(serialized["fallback_priority"], 2)
        self.assertEqual(serialized["capabilities"], config.capabilities)
        self.assertNotEqual(serialized["api_key"], config.api_key)
        self.assertNotIn(config.api_key, repr(serialized))


class ImageModelConfigDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_dynamic_openai_image_config_overrides_env_provider_settings(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"b64_json": VALID_IMAGE_B64}]}),
        )
        image_model_config = {
            "provider_type": "openai_image",
            "base_url": "https://dynamic.example.test",
            "model_name": "gpt-image-custom",
            "api_key": "dynamic-key",
        }

        from unittest.mock import patch

        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            image = await service._call_ai_image_api(
                "生成一张海报",
                provider_override="doubao",
                image_model_config=image_model_config,
            )

        self.assertEqual(image, VALID_IMAGE_B64)
        self.assertEqual(client.post_payload["model"], "gpt-image-custom")

    async def test_dynamic_openai_image_config_uses_edits_endpoint_with_input_image(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"b64_json": VALID_IMAGE_B64}]}),
        )
        image_model_config = {
            "provider_type": "openai_image",
            "base_url": "https://dynamic.example.test",
            "model_name": "gpt-image-custom",
            "api_key": "dynamic-key",
        }

        from unittest.mock import patch

        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            image = await service._call_ai_image_api(
                "把日期改成 7月9日，其他保持一致",
                input_image_base64=f"data:image/png;base64,{VALID_IMAGE_B64}",
                image_model_config=image_model_config,
            )

        self.assertEqual(image, VALID_IMAGE_B64)
        self.assertEqual(client.post_url, "https://dynamic.example.test/v1/images/edits")
        self.assertEqual(client.post_payload["model"], "gpt-image-custom")
        self.assertEqual(client.post_payload["prompt"], "把日期改成 7月9日，其他保持一致")
        self.assertIn("image", [name for name, _ in client.post_kwargs["files"]])
        self.assertNotEqual(client.post_kwargs["headers"].get("Content-Type"), "application/json")

    async def test_dynamic_openai_image_config_sends_all_reference_images_to_edits_endpoint(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"b64_json": VALID_IMAGE_B64}]}),
        )
        image_model_config = {
            "provider_type": "openai_image",
            "base_url": "https://dynamic.example.test",
            "model_name": "gpt-image-custom",
            "api_key": "dynamic-key",
        }

        from unittest.mock import patch

        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            image = await service._call_ai_image_api(
                "把图1和图2融合成一张海报",
                input_images_base64=[
                    f"data:image/png;base64,{VALID_IMAGE_B64}",
                    f"data:image/webp;base64,{VALID_IMAGE_B64}",
                ],
                image_model_config=image_model_config,
            )

        self.assertEqual(image, VALID_IMAGE_B64)
        self.assertEqual(client.post_url, "https://dynamic.example.test/v1/images/edits")
        image_files = [file for name, file in client.post_kwargs["files"] if name == "image"]
        self.assertEqual(len(image_files), 2)
        self.assertEqual(image_files[0][2], "image/png")
        self.assertEqual(image_files[1][2], "image/webp")


class ImageModelApiTests(unittest.TestCase):
    def test_image_model_router_is_registered(self):
        from app.main import app

        paths = {route.path for route in app.routes}

        self.assertIn("/api/v1/image-models/list", paths)


if __name__ == "__main__":
    unittest.main()
