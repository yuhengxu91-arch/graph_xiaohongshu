"""图片模型安全引用与运行时解析。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional
from uuid import UUID

from app.core.db import async_session_factory
from app.services.image_model_service import image_model_service


BUILTIN_MODEL_NAMES = {
    "gemini": "Gemini（系统内置）",
    "gemini_ch": "Gemini（changhuai）",
    "gpt_image": "GPT Image（系统内置）",
    "doubao": "豆包 Seedream",
}


@dataclass(frozen=True)
class ImageModelRef:
    """不包含供应商凭据、可安全持久化的图片模型引用。"""

    source: Literal["builtin", "config"]
    display_name: str
    provider: Optional[str] = None
    config_id: Optional[UUID] = None

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("图片模型显示名称不能为空")
        if self.source == "config":
            if not self.config_id or self.provider:
                raise ValueError("公共模型引用必须包含 config_id 且不能包含 provider")
            return
        if self.source == "builtin":
            if not self.provider or self.config_id:
                raise ValueError("内置模型引用必须包含 provider 且不能包含 config_id")
            if self.provider not in BUILTIN_MODEL_NAMES:
                raise ValueError(f"不支持的内置图片模型: {self.provider}")
            return
        raise ValueError(f"不支持的图片模型引用来源: {self.source}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "display_name": self.display_name,
            "provider": self.provider,
            "config_id": str(self.config_id) if self.config_id else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ImageModelRef":
        if not isinstance(payload, dict):
            raise ValueError("图片模型引用格式无效")
        raw_config_id = payload.get("config_id")
        try:
            config_id = UUID(str(raw_config_id)) if raw_config_id else None
        except (TypeError, ValueError) as exc:
            raise ValueError("图片模型 config_id 无效") from exc
        return cls(
            source=payload.get("source"),
            display_name=str(payload.get("display_name") or "").strip(),
            provider=payload.get("provider"),
            config_id=config_id,
        )


async def resolve_runtime_config(
    db: Any,
    model_ref: ImageModelRef | dict[str, Any],
) -> dict[str, Any]:
    """在执行阶段将安全引用解析为短生命周期运行时配置。"""
    ref = (
        ImageModelRef.from_dict(model_ref)
        if isinstance(model_ref, dict)
        else model_ref
    )
    if ref.source == "builtin":
        return {
            "provider_override": ref.provider,
            "image_model_config": None,
            "display_name": ref.display_name,
        }

    config = await image_model_service.get_config(
        db,
        config_id=ref.config_id,
        active_only=True,
    )
    if not config:
        raise ValueError("选择的图片模型不存在或已停用")
    return {
        "provider_override": None,
        "image_model_config": image_model_service.runtime_config(config),
        "display_name": config.name,
    }


async def resolve_runtime_config_with_session(
    model_ref: ImageModelRef | dict[str, Any],
) -> dict[str, Any]:
    """使用独立短会话解析模型，关闭会话后再由调用方请求第三方服务。"""
    async with async_session_factory() as session:
        return await resolve_runtime_config(session, model_ref)
