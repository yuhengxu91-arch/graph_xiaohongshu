"""
个人中心服务层
负责用户资料 CRUD、头像上传、密码修改、创作统计聚合、偏好管理
"""
from __future__ import annotations

import base64
import uuid as uuid_mod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password, get_password_hash
from app.models.user import User, UserPreference
from app.models.poster import PosterGeneration, PosterTemplate
from app.models.brand import BrandKit


class ProfileService:
    """个人中心服务"""

    def __init__(self) -> None:
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.static_root = self.project_root / "static"

    # =====================================================
    # 个人资料
    # =====================================================
    async def get_profile(self, db: AsyncSession, *, user_id: UUID) -> dict[str, Any]:
        """获取用户完整个人资料"""
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return {}
        return self._serialize_profile(user)

    async def update_profile(
        self, db: AsyncSession, *, user_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any]:
        """更新个人资料（昵称、简介）"""
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return {}

        updatable = ["nickname", "bio"]
        for field in updatable:
            if field in data:
                setattr(user, field, data[field])

        user.updated_at = datetime.utcnow()
        await db.flush()
        await db.refresh(user)
        return self._serialize_profile(user)

    # =====================================================
    # 头像上传
    # =====================================================
    async def upload_avatar(
        self, db: AsyncSession, *, user_id: UUID,
        avatar_base64: str, content_type: str = "image/png"
    ) -> str:
        """保存头像并更新 User.avatar_url"""
        ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
        ext = ext_map.get(content_type, ".png")

        upload_dir = self.static_root / "avatars"
        upload_dir.mkdir(parents=True, exist_ok=True)

        filename = f"avatar_{user_id}_{uuid_mod.uuid4().hex[:8]}{ext}"
        filepath = upload_dir / filename
        image_data = base64.b64decode(avatar_base64)
        filepath.write_bytes(image_data)

        avatar_url = f"/static/avatars/{filename}"

        # 更新用户记录
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            # 清理旧头像
            if user.avatar_url:
                old_path = self.project_root / user.avatar_url.lstrip("/")
                if old_path.exists():
                    try:
                        old_path.unlink()
                    except OSError:
                        pass
            user.avatar_url = avatar_url
            user.updated_at = datetime.utcnow()
            await db.flush()

        return avatar_url

    # =====================================================
    # 修改密码
    # =====================================================
    async def change_password(
        self, db: AsyncSession, *, user_id: UUID,
        old_password: str, new_password: str
    ) -> bool:
        """验证旧密码并更新为新密码，成功返回 True"""
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return False

        if not verify_password(old_password, user.password_hash):
            raise ValueError("旧密码错误")

        user.password_hash = get_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        await db.flush()
        return True

    # =====================================================
    # 创作统计
    # =====================================================
    async def get_stats(self, db: AsyncSession, *, user_id: UUID) -> dict[str, Any]:
        """聚合查询用户创作数据"""

        # 1) 总作品数 & 收藏数 & 存储量
        basic_stmt = select(
            func.count(PosterGeneration.id).label("total_works"),
            func.sum(
                case((PosterGeneration.is_favorite == True, 1), else_=0)
            ).label("total_favorites"),
            func.coalesce(func.sum(PosterGeneration.file_size), 0).label("storage_used_bytes"),
        ).where(
            PosterGeneration.user_id == user_id,
            PosterGeneration.success == True,
        )
        basic = (await db.execute(basic_stmt)).one()

        # 2) 个人模板数
        tpl_stmt = select(func.count(PosterTemplate.id)).where(
            PosterTemplate.user_id == user_id,
            PosterTemplate.is_system == False,
        )
        total_templates = (await db.execute(tpl_stmt)).scalar() or 0

        # 3) 模式分布
        mode_stmt = select(
            PosterGeneration.mode,
            func.count(PosterGeneration.id)
        ).where(
            PosterGeneration.user_id == user_id,
            PosterGeneration.success == True,
        ).group_by(PosterGeneration.mode)
        mode_rows = (await db.execute(mode_stmt)).all()
        mode_distribution = {row[0]: row[1] for row in mode_rows}

        # 4) 近 7 天趋势
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        trend_stmt = select(
            func.date(PosterGeneration.created_at).label("day"),
            func.count(PosterGeneration.id)
        ).where(
            PosterGeneration.user_id == user_id,
            PosterGeneration.success == True,
            PosterGeneration.created_at >= seven_days_ago,
        ).group_by("day").order_by("day")
        trend_rows = (await db.execute(trend_stmt)).all()
        recent_trend = [
            {"date": str(row[0]), "count": row[1]} for row in trend_rows
        ]

        # 5) 品牌包状态
        brand_stmt = select(func.count(BrandKit.id)).where(BrandKit.user_id == user_id)
        brand_configured = ((await db.execute(brand_stmt)).scalar() or 0) > 0

        return {
            "total_works": basic.total_works or 0,
            "total_favorites": basic.total_favorites or 0,
            "total_templates": total_templates,
            "storage_used_bytes": basic.storage_used_bytes or 0,
            "mode_distribution": mode_distribution,
            "recent_trend": recent_trend,
            "brand_kit_configured": brand_configured,
        }

    # =====================================================
    # 偏好设置
    # =====================================================
    async def get_preferences(self, db: AsyncSession, *, user_id: UUID) -> dict[str, Any]:
        """获取用户偏好设置"""
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await db.execute(stmt)
        pref = result.scalar_one_or_none()
        if pref is None:
            return {
                "default_aspect_ratio": "3:4",
                "default_mode": "custom",
                "default_style_tag": None,
                "auto_save_to_gallery": True,
                "custom_api_key": "",
            }
        return self._serialize_prefs(pref)

    async def update_preferences(
        self, db: AsyncSession, *, user_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any]:
        """创建或更新用户偏好设置"""
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await db.execute(stmt)
        pref = result.scalar_one_or_none()

        if pref is None:
            pref = UserPreference(user_id=user_id)
            db.add(pref)

        updatable = [
            "default_aspect_ratio", "default_mode",
            "default_style_tag", "auto_save_to_gallery",
            "custom_api_key",
        ]
        for field in updatable:
            if field in data:
                setattr(pref, field, data[field])

        pref.updated_at = datetime.utcnow()
        await db.flush()
        await db.refresh(pref)
        return self._serialize_prefs(pref)

    # =====================================================
    # 序列化
    # =====================================================
    def _serialize_profile(self, user: User) -> dict[str, Any]:
        return {
            "id": str(user.id),
            "username": user.username,
            "avatar_url": user.avatar_url,
            "nickname": user.nickname or user.username,
            "bio": user.bio,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }

    def _serialize_prefs(self, pref: UserPreference) -> dict[str, Any]:
        return {
            "default_aspect_ratio": pref.default_aspect_ratio,
            "default_mode": pref.default_mode,
            "default_style_tag": pref.default_style_tag,
            "auto_save_to_gallery": pref.auto_save_to_gallery,
            "custom_api_key": "***" if pref.custom_api_key else "",
        }


# 模块级单例
profile_service = ProfileService()
