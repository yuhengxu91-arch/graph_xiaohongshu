import unittest

from tests.test_poster_service import FakeAsyncClient, FakeResponse
from app.services.poster_service import PosterService


class ImageModelConfigDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_dynamic_openai_image_config_overrides_env_provider_settings(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"b64_json": "dynamic-image"}]}),
        )
        image_model_config = {
            "provider_type": "openai_image",
            "base_url": "https://dynamic.example.test",
            "model_name": "gpt-image-custom",
            "api_key": "dynamic-key",
        }

        from unittest.mock import patch

        with patch("app.services.poster_service.httpx.AsyncClient", return_value=client):
            image = await service._call_ai_image_api(
                "生成一张海报",
                provider_override="doubao",
                image_model_config=image_model_config,
            )

        self.assertEqual(image, "dynamic-image")
        self.assertEqual(client.post_payload["model"], "gpt-image-custom")


class ImageModelApiTests(unittest.TestCase):
    def test_image_model_router_is_registered(self):
        from app.main import app

        paths = {route.path for route in app.routes}

        self.assertIn("/api/v1/image-models/list", paths)


if __name__ == "__main__":
    unittest.main()
