import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.services.admin_service import AdminService


class FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeAdminSession:
    def __init__(self, first_user_id):
        self.first_user_id = first_user_id

    async def execute(self, _stmt):
        return FakeScalarResult(self.first_user_id)


class AdminServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_with_database_admin_flag_is_admin(self):
        service = AdminService()

        with patch("app.services.admin_service.settings.admin_usernames", ""):
            result = await service.is_admin(
                FakeAdminSession(first_user_id=uuid4()),
                SimpleNamespace(id=uuid4(), username="ops", is_admin=True),
            )

        self.assertTrue(result)

    async def test_configured_admin_username_is_admin(self):
        service = AdminService()

        with patch("app.services.admin_service.settings.admin_usernames", "admin,operator"):
            result = await service.is_admin(
                FakeAdminSession(first_user_id=uuid4()),
                SimpleNamespace(id=uuid4(), username="operator"),
            )

        self.assertTrue(result)

    async def test_first_created_user_is_admin_without_configured_username(self):
        service = AdminService()
        first_user_id = uuid4()

        with patch("app.services.admin_service.settings.admin_usernames", ""):
            result = await service.is_admin(
                FakeAdminSession(first_user_id=first_user_id),
                SimpleNamespace(id=first_user_id, username="lee"),
            )

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
