import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException
from app.services.user_admin_service import LastActiveAdminError, UserAdminService


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class ScalarsResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values


class LockSession:
    def __init__(self, active_admins):
        self.active_admins = active_admins
        self.flush = AsyncMock()

    async def execute(self, _statement):
        return ScalarsResult(self.active_admins)


class BasicUserManagementTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_rejects_inactive_user(self):
        from app.api.v1 import auth as auth_api

        user = SimpleNamespace(
            id=uuid4(), username="disabled", password_hash="hash", is_active=False,
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=ScalarResult(user)))
        with patch.object(auth_api, "verify_password", return_value=True):
            with self.assertRaises(HTTPException) as ctx:
                await auth_api.login(auth_api.LoginRequest(username="disabled", password="secret"), db)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "账号已停用，请联系管理员")

    async def test_required_auth_rejects_inactive_token_owner(self):
        from app.dependencies import auth as auth_dependency

        user = SimpleNamespace(id=uuid4(), is_active=False)
        db = SimpleNamespace(execute=AsyncMock(return_value=ScalarResult(user)))
        credentials = SimpleNamespace(credentials="token")
        with patch.object(auth_dependency, "decode_access_token", return_value={"sub": str(user.id)}):
            with self.assertRaises(HTTPException) as ctx:
                await auth_dependency.get_current_user(credentials, db)

        self.assertEqual(ctx.exception.status_code, 403)

    async def test_optional_auth_rejects_inactive_token_owner(self):
        from app.dependencies import auth as auth_dependency

        user = SimpleNamespace(id=uuid4(), is_active=False)
        db = SimpleNamespace(execute=AsyncMock(return_value=ScalarResult(user)))
        credentials = SimpleNamespace(credentials="token")
        with patch.object(auth_dependency, "decode_access_token", return_value={"sub": str(user.id)}):
            with self.assertRaises(HTTPException) as ctx:
                await auth_dependency.get_current_user_optional(credentials, db)

        self.assertEqual(ctx.exception.status_code, 403)

    def test_public_register_route_is_removed(self):
        from app.api.v1 import auth as auth_api

        paths = {route.path for route in auth_api.router.routes}
        self.assertNotIn("/auth/register", paths)

    def test_user_model_has_active_flag(self):
        from app.models.user import User

        self.assertIn("is_active", User.__table__.columns)

    async def test_last_active_admin_cannot_be_demoted(self):
        service = UserAdminService()
        admin = SimpleNamespace(id=uuid4(), is_admin=True, is_active=True)

        with self.assertRaises(LastActiveAdminError):
            await service.set_user_admin(LockSession([admin]), admin.id, False)

    async def test_last_active_admin_cannot_be_disabled(self):
        service = UserAdminService()
        admin = SimpleNamespace(id=uuid4(), is_admin=True, is_active=True)

        with self.assertRaises(LastActiveAdminError):
            await service.set_user_status(LockSession([admin]), admin.id, False)

    async def test_one_of_two_active_admins_can_be_disabled(self):
        service = UserAdminService()
        target = SimpleNamespace(id=uuid4(), is_admin=True, is_active=True)
        other = SimpleNamespace(id=uuid4(), is_admin=True, is_active=True)
        session = LockSession([target, other])

        result = await service.set_user_status(session, target.id, False)

        self.assertIs(result, target)
        self.assertFalse(target.is_active)
        session.flush.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
