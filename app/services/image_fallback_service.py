"""图片模型安全引用与运行时解析。"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, Optional
from uuid import UUID

from app.core.db import async_session_factory
from app.services.image_generation_errors import ImageGenerationError
from app.services.image_model_service import image_model_service

logger = logging.getLogger(__name__)

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


@dataclass(frozen=True)
class GenerationContext:
    """一次模型调用链的安全关联信息。"""

    chain_id: str
    task_id: Optional[str] = None
    item_id: Optional[str] = None
    user_id: Optional[str] = None


@dataclass(frozen=True)
class GenerationOutcome:
    """包含降级来源的图片生成结果。"""

    image_base64: str
    degraded: bool
    requested_model_name: str
    actual_model_name: str
    fallback_attempts: int


EDIT_MODES = {"edit", "style_transfer", "outpaint", "adapt"}
MASK_EDIT_MODES = {"inpaint", "erase"}
REFERENCE_MODES = {"custom", "template", "export_all"}


def derive_required_capabilities(
    mode: str,
    *,
    reference_count: int = 0,
    aspect_ratio: Optional[str] = None,
) -> dict[str, Any]:
    """从业务模式推导备用模型必须具备的能力。"""
    normalized_mode = (mode or "custom").strip().lower()
    required: dict[str, Any] = {}
    if normalized_mode in MASK_EDIT_MODES:
        required.update(image_edit=True, mask_edit=True)
    elif normalized_mode in EDIT_MODES:
        required["image_edit"] = True
    elif normalized_mode in REFERENCE_MODES:
        if reference_count > 1:
            required["multiple_references"] = True
        elif reference_count == 1:
            required["single_reference"] = True
        else:
            required["text_to_image"] = True
    else:
        required["text_to_image"] = True
    if aspect_ratio:
        required["aspect_ratio"] = aspect_ratio
    return required


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


CandidateLoader = Callable[
    [ImageModelRef, dict[str, Any]],
    Awaitable[list[ImageModelRef]],
]
RuntimeResolver = Callable[[ImageModelRef], Awaitable[dict[str, Any]]]
ImageInvoker = Callable[[dict[str, Any]], Awaitable[str]]


class ImageFallbackService:
    """主模型临时失败时按管理员顺序尝试备用公共模型。"""

    def __init__(
        self,
        *,
        candidate_loader: Optional[CandidateLoader] = None,
        runtime_resolver: Optional[RuntimeResolver] = None,
    ) -> None:
        self._candidate_loader = candidate_loader or self._load_candidates
        self._runtime_resolver = runtime_resolver or resolve_runtime_config_with_session

    async def _load_candidates(
        self,
        primary_ref: ImageModelRef,
        required_capabilities: dict[str, Any],
    ) -> list[ImageModelRef]:
        async with async_session_factory() as session:
            return await image_model_service.list_fallback_model_refs(
                session,
                primary_ref=primary_ref,
                required_capabilities=required_capabilities,
            )

    async def generate(
        self,
        *,
        primary_ref: ImageModelRef,
        required_capabilities: dict[str, Any],
        invoke: ImageInvoker,
        context: GenerationContext,
    ) -> GenerationOutcome:
        requested_name = primary_ref.display_name
        primary_runtime = await self._runtime_resolver(primary_ref)
        try:
            image = await invoke(primary_runtime)
            return GenerationOutcome(
                image_base64=image,
                degraded=False,
                requested_model_name=requested_name,
                actual_model_name=requested_name,
                fallback_attempts=0,
            )
        except asyncio.CancelledError:
            raise
        except ImageGenerationError as error:
            self._log_attempt(
                context=context,
                model_ref=primary_ref,
                error=error,
                attempt=0,
                elapsed_ms=None,
            )
            if not error.retryable:
                raise
            last_error = error

        candidates = await self._candidate_loader(
            primary_ref, required_capabilities
        )
        fallback_attempts = 0
        for candidate in candidates:
            current_candidates = await self._candidate_loader(
                primary_ref, required_capabilities
            )
            current_candidate = next(
                (
                    current
                    for current in current_candidates
                    if self._same_model(candidate, current)
                ),
                None,
            )
            if current_candidate is None:
                continue
            candidate = current_candidate
            try:
                runtime = await self._runtime_resolver(candidate)
            except asyncio.CancelledError:
                raise
            except (ValueError, LookupError):
                continue

            fallback_attempts += 1
            started = time.monotonic()
            try:
                image = await invoke(runtime)
                logger.info(
                    "image_fallback_succeeded",
                    extra=self._log_extra(
                        context,
                        candidate,
                        attempt=fallback_attempts,
                        elapsed_ms=(time.monotonic() - started) * 1000,
                    ),
                )
                return GenerationOutcome(
                    image_base64=image,
                    degraded=True,
                    requested_model_name=requested_name,
                    actual_model_name=candidate.display_name,
                    fallback_attempts=fallback_attempts,
                )
            except asyncio.CancelledError:
                raise
            except ImageGenerationError as error:
                last_error = error
                self._log_attempt(
                    context=context,
                    model_ref=candidate,
                    error=error,
                    attempt=fallback_attempts,
                    elapsed_ms=(time.monotonic() - started) * 1000,
                )
                if not error.retryable:
                    raise

        raise last_error

    @staticmethod
    def _same_model(left: ImageModelRef, right: ImageModelRef) -> bool:
        if left.source != right.source:
            return False
        if left.source == "config":
            return left.config_id == right.config_id
        return left.provider == right.provider

    def _log_extra(
        self,
        context: GenerationContext,
        model_ref: ImageModelRef,
        *,
        attempt: int,
        elapsed_ms: Optional[float],
    ) -> dict[str, Any]:
        return {
            "chain_id": context.chain_id,
            "task_id": context.task_id,
            "item_id": context.item_id,
            "user_id": context.user_id,
            "model_config_id": (
                str(model_ref.config_id) if model_ref.config_id else None
            ),
            "provider": model_ref.provider,
            "attempt": attempt,
            "elapsed_ms": round(elapsed_ms, 2) if elapsed_ms is not None else None,
        }

    def _log_attempt(
        self,
        *,
        context: GenerationContext,
        model_ref: ImageModelRef,
        error: ImageGenerationError,
        attempt: int,
        elapsed_ms: Optional[float],
    ) -> None:
        logger.warning(
            "image_generation_attempt_failed",
            extra={
                **self._log_extra(
                    context,
                    model_ref,
                    attempt=attempt,
                    elapsed_ms=elapsed_ms,
                ),
                "error_category": error.category,
                "provider_status": error.provider_status,
                "retryable": error.retryable,
            },
        )


image_fallback_service = ImageFallbackService()
