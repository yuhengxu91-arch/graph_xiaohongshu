"""
后台管理 API
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.admin_service import admin_service
from app.services.user_admin_service import user_admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])


class AdminUserResponse(BaseModel):
    id: str
    username: str
    is_admin: bool
    created_at: Optional[datetime] = None


class SetUserAdminRequest(BaseModel):
    is_admin: bool = Field(..., description="是否授予管理员权限")


async def _ensure_admin(db: AsyncSession, current_user: User) -> None:
    if not await admin_service.is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问人员管理",
        )


def _serialize_user(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=str(user.id),
        username=user.username,
        is_admin=bool(getattr(user, "is_admin", False)),
        created_at=user.created_at,
    )


@router.get("/users", response_model=list[AdminUserResponse], summary="管理员查看用户列表")
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_admin(db, current_user)
    users = await user_admin_service.list_users(db)
    return [_serialize_user(user) for user in users]


@router.put("/users/{user_id}/admin", response_model=AdminUserResponse, summary="设置用户管理员权限")
async def set_user_admin(
    user_id: UUID,
    request: SetUserAdminRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_admin(db, current_user)
    if current_user.id == user_id and not request.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能取消自己的管理员权限",
        )

    user = await user_admin_service.set_user_admin(db, user_id, request.is_admin)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    return _serialize_user(user)
