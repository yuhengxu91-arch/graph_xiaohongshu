"""
全站公共图片模型配置 API
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.image_model_service import image_model_service

router = APIRouter(prefix="/image-models", tags=["Image Models"])


class ImageModelRequest(BaseModel):
    name: str = Field(..., max_length=100)
    provider_type: str = Field(..., description="openai_image / gemini / doubao")
    base_url: str = Field(..., max_length=500)
    model_name: str = Field(..., max_length=120)
    api_key: str = Field(..., max_length=500)
    description: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    sort_order: int = 0
    fallback_enabled: bool = False
    fallback_priority: Optional[int] = Field(default=None, ge=1)
    capabilities: Dict[str, Any] = Field(default_factory=dict)


class ImageModelUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    provider_type: Optional[str] = None
    base_url: Optional[str] = Field(default=None, max_length=500)
    model_name: Optional[str] = Field(default=None, max_length=120)
    api_key: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None
    fallback_enabled: Optional[bool] = None
    fallback_priority: Optional[int] = Field(default=None, ge=1)
    capabilities: Optional[Dict[str, Any]] = None


async def _ensure_admin(db: AsyncSession, current_user: User) -> None:
    if not await image_model_service.is_admin(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以管理图片模型",
        )


@router.get("/list", summary="获取图片模型列表")
async def list_image_models(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    can_manage = await image_model_service.is_admin(db, current_user)
    configs = await image_model_service.list_configs(
        db,
        include_inactive=include_inactive and can_manage,
    )
    return {
        "items": [image_model_service.serialize(config) for config in configs],
        "can_manage": can_manage,
        "provider_types": [
            {"value": "openai_image", "label": "OpenAI Image 兼容"},
            {"value": "gemini", "label": "Gemini"},
            {"value": "doubao", "label": "豆包 Seedream"},
        ],
    }


@router.post("/create", summary="新增图片模型")
async def create_image_model(
    request: ImageModelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_admin(db, current_user)
    try:
        config = await image_model_service.create_config(db, request.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return image_model_service.serialize(config)


@router.put("/{config_id}", summary="更新图片模型")
async def update_image_model(
    config_id: UUID,
    request: ImageModelUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_admin(db, current_user)
    try:
        config = await image_model_service.update_config(
            db,
            config_id=config_id,
            data=request.model_dump(exclude_unset=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片模型不存在")
    return image_model_service.serialize(config)


@router.post("/{config_id}/set-default", summary="设为默认图片模型")
async def set_default_image_model(
    config_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_admin(db, current_user)
    config = await image_model_service.set_default(db, config_id=config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片模型不存在")
    return image_model_service.serialize(config)


@router.delete("/{config_id}", summary="删除图片模型")
async def delete_image_model(
    config_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_admin(db, current_user)
    deleted = await image_model_service.delete_config(db, config_id=config_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片模型不存在")
    return {"success": True, "deleted_count": 1}


@router.get("/channels", summary="获取所有可测试的模型通道")
async def list_model_channels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """返回所有公共配置模型的通道列表，仅管理员可用。"""
    await _ensure_admin(db, current_user)

    channels = []

    # 公共配置模型
    configs = await image_model_service.list_configs(db, include_inactive=False)
    for config in configs:
        channels.append({
            "id": f"config:{config.id}",
            "name": config.name,
            "source": "config",
            "provider": None,
            "provider_type": config.provider_type,
            "model_name": config.model_name,
            "base_url": config.base_url,
        })

    return {"channels": channels}


@router.post("/test/{channel_id}", summary="测试模型通道连通性")
async def test_model_channel(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """对指定通道发送极简文生图请求，检测通道是否正常。仅管理员可用。"""
    await _ensure_admin(db, current_user)

    from app.services.poster_service import poster_service

    if channel_id.startswith("builtin:"):
        provider = channel_id.replace("builtin:", "")
        result = await poster_service.test_channel(
            provider_override=provider,
        )
    elif channel_id.startswith("config:"):
        config_id_str = channel_id.replace("config:", "")
        try:
            config_id = UUID(config_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的模型配置 ID",
            )
        config = await image_model_service.get_config(
            db, config_id=config_id, active_only=True,
        )
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模型配置不存在或已停用",
            )
        result = await poster_service.test_channel(
            image_model_config=image_model_service.runtime_config(config),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的通道标识符",
        )

    return result
