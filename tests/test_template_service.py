import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.services.template_service import TemplateService


class FakeSession:
    def __init__(self):
        self.added = []
        self.flush = AsyncMock()
        self.refresh = AsyncMock()

    def add(self, obj):
        self.added.append(obj)


class TemplateServicePublishTests(unittest.IsolatedAsyncioTestCase):
    async def test_publish_template_copies_owned_personal_template_to_public(self):
        service = TemplateService()
        user_id = uuid4()
        source = SimpleNamespace(
            user_id=user_id,
            is_system=False,
            name="喜报",
            description="喜报模板",
            category="通用",
            style_tag="庆祝",
            config={"text_slots": [{"name": "title"}]},
            thumbnail_url="/static/thumb.png",
            source_generation_id=uuid4(),
        )
        service.get_template = AsyncMock(return_value=source)
        db = FakeSession()

        published = await service.publish_template(db, user_id=user_id, template_id=uuid4())

        self.assertIsNotNone(published)
        self.assertEqual(db.added, [published])
        self.assertIsNone(published.user_id)
        self.assertTrue(published.is_system)
        self.assertEqual(published.name, "喜报")
        self.assertEqual(published.config, source.config)
        self.assertIsNot(published.config, source.config)
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once_with(published)

    async def test_publish_template_rejects_unowned_template(self):
        service = TemplateService()
        source = SimpleNamespace(user_id=uuid4(), is_system=False)
        service.get_template = AsyncMock(return_value=source)

        published = await service.publish_template(FakeSession(), user_id=uuid4(), template_id=uuid4())

        self.assertIsNone(published)


if __name__ == "__main__":
    unittest.main()
