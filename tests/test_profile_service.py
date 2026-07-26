import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.services.image_fallback_service import ImageModelRef
from app.services.profile_service import ProfileService


class ProfileServiceTests(unittest.TestCase):
    def test_serialize_preferences_drops_removed_image_provider(self):
        service = ProfileService()
        pref = SimpleNamespace(
            default_aspect_ratio="3:4",
            default_mode="custom",
            default_style_tag=None,
            auto_save_to_gallery=True,
            image_provider="jimeng",
            image_model_config_id=None,
            custom_api_key="legacy-key",
        )

        data = service._serialize_prefs(pref)

        self.assertIsNone(data["image_provider"])
        self.assertNotIn("custom_api_key", data)


class ProfileServiceImageModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_removed_image_provider_falls_back_to_system_default(self):
        service = ProfileService()
        result = SimpleNamespace(scalar_one_or_none=lambda: "jimeng")
        db = SimpleNamespace(execute=AsyncMock(return_value=result))

        provider = await service.get_user_image_provider(db, user_id=uuid4())

        self.assertIsNone(provider)

    async def test_selected_public_model_returns_safe_reference(self):
        service = ProfileService()
        config_id = uuid4()
        result = SimpleNamespace(scalar_one_or_none=lambda: config_id)
        db = SimpleNamespace(execute=AsyncMock(return_value=result))
        config = SimpleNamespace(id=config_id, name="公共模型", provider_type="openai_image")

        with patch(
            "app.services.image_model_service.image_model_service.get_config",
            AsyncMock(return_value=config),
        ):
            model_ref = await service.get_user_image_model_config(db, user_id=uuid4())

        self.assertIsInstance(model_ref, ImageModelRef)
        self.assertEqual(model_ref.config_id, config_id)
        self.assertNotIn("api_key", model_ref.to_dict())
        self.assertNotIn("base_url", model_ref.to_dict())


if __name__ == "__main__":
    unittest.main()
