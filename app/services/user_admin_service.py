"""
后台用户管理服务
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserAdminService:
    async def list_users(self, db: AsyncSession) -> list[User]:
        stmt = select(User).order_by(User.is_admin.desc(), asc(User.created_at))
        return (await db.execute(stmt)).scalars().all()

    async def get_user(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def set_user_admin(self, db: AsyncSession, user_id: UUID, is_admin: bool) -> Optional[User]:
        user = await self.get_user(db, user_id)
        if user is None:
            return None
        user.is_admin = is_admin
        await db.flush()
        await db.refresh(user)
        return user


user_admin_service = UserAdminService()
