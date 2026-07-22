import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.services.prompt_service import PromptService


class FakeSession:
    def __init__(self):
        self.flush = AsyncMock()
        self.refresh = AsyncMock()


class PromptUnpublishServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_can_unpublish_without_deleting_prompt_data(self):
        service = PromptService()
        user_id = uuid4()
        snippet = SimpleNamespace(
            user_id=user_id,
            is_public=True,
            content="保留的提示词内容",
            use_count=12,
            is_active=True,
            updated_at=None,
        )
        service.get_prompt = AsyncMock(return_value=snippet)
        db = FakeSession()

        result = await service.unpublish_prompt(
            db,
            user_id=user_id,
            prompt_id=uuid4(),
        )

        self.assertIs(result, snippet)
        self.assertFalse(snippet.is_public)
        self.assertEqual(snippet.content, "保留的提示词内容")
        self.assertEqual(snippet.use_count, 12)
        self.assertTrue(snippet.is_active)
        self.assertIsNotNone(snippet.updated_at)
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once_with(snippet)

    async def test_non_owner_cannot_unpublish_prompt(self):
        service = PromptService()
        snippet = SimpleNamespace(
            user_id=uuid4(),
            is_public=True,
            updated_at=None,
        )
        service.get_prompt = AsyncMock(return_value=snippet)
        db = FakeSession()

        result = await service.unpublish_prompt(
            db,
            user_id=uuid4(),
            prompt_id=uuid4(),
        )

        self.assertIsNone(result)
        self.assertTrue(snippet.is_public)
        db.flush.assert_not_awaited()
        db.refresh.assert_not_awaited()


class PromptUnpublishApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_unpublish_route_returns_serialized_prompt(self):
        from app.api.v1 import prompt as prompt_api

        prompt_id = uuid4()
        user_id = uuid4()
        snippet = SimpleNamespace(id=prompt_id, is_public=False)
        serialized = {"id": str(prompt_id), "is_public": False}

        with patch.object(
            prompt_api.prompt_service,
            "unpublish_prompt",
            AsyncMock(return_value=snippet),
        ) as unpublish_mock:
            with patch.object(
                prompt_api.prompt_service,
                "serialize",
                return_value=serialized,
            ):
                result = await prompt_api.unpublish_prompt(
                    prompt_id,
                    current_user=SimpleNamespace(id=user_id),
                    db=object(),
                )

        self.assertEqual(result, serialized)
        unpublish_mock.assert_awaited_once_with(
            unittest.mock.ANY,
            user_id=user_id,
            prompt_id=prompt_id,
        )

    async def test_unpublish_route_returns_not_found_for_non_owner(self):
        from app.api.v1 import prompt as prompt_api

        with patch.object(
            prompt_api.prompt_service,
            "unpublish_prompt",
            AsyncMock(return_value=None),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await prompt_api.unpublish_prompt(
                    uuid4(),
                    current_user=SimpleNamespace(id=uuid4()),
                    db=object(),
                )

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "提示词不存在或无权撤回")


if __name__ == "__main__":
    unittest.main()
