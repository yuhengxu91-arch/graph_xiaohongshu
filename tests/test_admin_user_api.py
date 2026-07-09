import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException


class AdminUserApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_users_requires_admin(self):
        from app.api.v1 import admin as admin_api

        with patch.object(admin_api.admin_service, "is_admin", AsyncMock(return_value=False)):
            with self.assertRaises(HTTPException) as ctx:
                await admin_api.list_users(
                    current_user=SimpleNamespace(id=uuid4(), username="lee"),
                    db=object(),
                )

        self.assertEqual(ctx.exception.status_code, 403)

    async def test_admin_can_grant_admin_to_user(self):
        from app.api.v1 import admin as admin_api

        target = SimpleNamespace(
            id=uuid4(),
            username="ops",
            is_admin=True,
            created_at=datetime(2026, 1, 1),
        )

        with patch.object(admin_api.admin_service, "is_admin", AsyncMock(return_value=True)):
            with patch.object(admin_api.user_admin_service, "set_user_admin", AsyncMock(return_value=target)) as set_mock:
                result = await admin_api.set_user_admin(
                    target.id,
                    admin_api.SetUserAdminRequest(is_admin=True),
                    current_user=SimpleNamespace(id=uuid4(), username="admin"),
                    db=object(),
                )

        set_mock.assert_awaited_once()
        self.assertTrue(result.is_admin)

    async def test_admin_cannot_demote_self(self):
        from app.api.v1 import admin as admin_api

        user_id = uuid4()
        with patch.object(admin_api.admin_service, "is_admin", AsyncMock(return_value=True)):
            with self.assertRaises(HTTPException) as ctx:
                await admin_api.set_user_admin(
                    user_id,
                    admin_api.SetUserAdminRequest(is_admin=False),
                    current_user=SimpleNamespace(id=user_id, username="admin"),
                    db=object(),
                )

        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
