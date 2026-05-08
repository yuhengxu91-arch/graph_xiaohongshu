import unittest
from types import SimpleNamespace

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
            custom_api_key=None,
        )

        data = service._serialize_prefs(pref)

        self.assertIsNone(data["image_provider"])


if __name__ == "__main__":
    unittest.main()
