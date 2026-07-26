import unittest
from unittest.mock import AsyncMock
from uuid import uuid4

from app.services.batch_service import BatchService, _tasks


class BatchTaskAccessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _tasks.clear()
        self.service = BatchService()
        self.service._persist_task_create = AsyncMock()

    async def asyncTearDown(self):
        _tasks.clear()

    async def test_anonymous_task_returns_token_and_persists_only_hash(self):
        result = await self.service.create_batch_task(
            [{"prompt": "测试"}],
            {"mode": "custom"},
        )

        token = result["access_token"]
        task = _tasks[result["task_id"]]
        self.assertTrue(token)
        self.assertNotEqual(task["access_token_hash"], token)
        self.assertNotIn(token, str(task))
        self.assertTrue(
            self.service.can_access_task(
                result["task_id"],
                access_token=token,
            )
        )
        self.assertFalse(
            self.service.can_access_task(
                result["task_id"],
                access_token="wrong-token",
            )
        )

    async def test_owned_task_allows_owner_and_admin_only(self):
        owner_id = uuid4()
        other_id = uuid4()
        result = await self.service.create_batch_task(
            [{"prompt": "测试"}],
            {"mode": "custom"},
            user_id=owner_id,
        )

        self.assertIsNone(result["access_token"])
        self.assertTrue(
            self.service.can_access_task(
                result["task_id"],
                user_id=owner_id,
            )
        )
        self.assertFalse(
            self.service.can_access_task(
                result["task_id"],
                user_id=other_id,
            )
        )
        self.assertTrue(
            self.service.can_access_task(
                result["task_id"],
                user_id=other_id,
                is_admin=True,
            )
        )

