"""
通用管理员权限服务
"""
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User


class AdminService:
    """基于配置和首个用户的轻量管理员判断。"""

    async def is_admin(self, db: AsyncSession, user: User) -> bool:
        if bool(getattr(user, "is_admin", False)):
            return True

        configured = {
            name.strip()
            for name in settings.admin_usernames.split(",")
            if name.strip()
        }
        if user.username in configured:
            return True

        result = await db.execute(select(User.id).order_by(asc(User.created_at)).limit(1))
        first_user_id = result.scalar_one_or_none()
        return first_user_id == user.id


admin_service = AdminService()
