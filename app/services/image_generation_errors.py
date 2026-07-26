"""图片供应商错误的安全分类。

该模块只保留降级决策所需的结构化字段，不携带第三方完整响应、
请求地址、提示词或凭据。
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import io
import re
from typing import Any, Mapping, Optional

import httpx


class ImageGenerationError(RuntimeError):
    """可安全返回给上层的图片生成错误。"""

    def __init__(
        self,
        category: str,
        safe_message: str,
        *,
        retryable: bool = False,
        provider_status: Optional[int] = None,
        internal_code: Optional[str] = None,
    ) -> None:
        super().__init__(safe_message)
        self.category = category
        self.safe_message = safe_message
        self.retryable = retryable
        self.provider_status = provider_status
        self.internal_code = internal_code


SAFE_MESSAGES = {
    "connection": "图片服务暂时无法连接",
    "timeout": "图片服务响应超时",
    "rate_limit": "图片服务当前繁忙",
    "server_error": "图片服务暂时不可用",
    "empty_result": "图片服务未返回有效图片",
    "download_error": "生成图片下载失败",
    "invalid_image": "图片服务返回了无效图片",
    "auth": "图片服务鉴权失败，请联系管理员",
    "quota": "图片服务额度不足，请联系管理员",
    "moderation": "图片内容未通过安全审核",
    "invalid_request": "图片生成参数无效",
    "provider_error": "图片生成失败",
}

RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
RETRYABLE_DOWNLOAD_STATUSES = {404, 408, 429, 500, 502, 503, 504}

MODERATION_TOKENS = {
    "safety",
    "prohibited_content",
    "content_policy_violation",
    "content_policy",
    "moderation",
    "blocked",
    "blocklist",
    "spii",
    "image_safety",
}
QUOTA_TOKENS = {
    "insufficient_quota",
    "quota_exceeded",
    "billing",
    "balance",
    "credit",
    "funds",
    "余额",
    "额度不足",
}
AUTH_TOKENS = {
    "invalid_api_key",
    "authentication",
    "unauthorized",
    "forbidden",
    "permission_denied",
    "鉴权",
}
INVALID_REQUEST_TOKENS = {
    "invalid_request",
    "invalid_parameter",
    "invalid_size",
    "bad_request",
    "unprocessable",
    "unsupported",
}
RATE_LIMIT_TOKENS = {
    "rate_limit",
    "rate_limit_exceeded",
    "too_many_requests",
    "throttled",
    "throttling",
}
SERVER_ERROR_TOKENS = {
    "server_error",
    "service_unavailable",
    "internal_error",
    "upstream_error",
    "temporarily_unavailable",
    "timeout",
}


def _normalize_token(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", text.lower()).strip("_")


def _contains_any(text: str, tokens: set[str]) -> bool:
    return any(token in text for token in tokens)


def _error_fields(error: Any) -> tuple[str, str]:
    if isinstance(error, Mapping):
        code = error.get("code") or error.get("type") or error.get("status") or ""
        message = error.get("message") or error.get("localized_message") or ""
        return _normalize_token(code), _normalize_token(message)
    if isinstance(error, str):
        return "", _normalize_token(error)
    return "", ""


def _extract_provider_error(provider: str, payload: Any) -> Any:
    if not isinstance(payload, Mapping):
        return None
    if payload.get("error"):
        return payload["error"]

    if provider == "doubao":
        data = payload.get("data")
        if isinstance(data, Mapping) and data.get("error"):
            return data["error"]
        items = data if isinstance(data, list) else None
        if isinstance(data, Mapping) and isinstance(data.get("data"), list):
            items = data["data"]
        for item in items or payload.get("images") or []:
            if isinstance(item, Mapping) and item.get("error"):
                return item["error"]
    return None


def _gemini_moderation_signal(payload: Any) -> Optional[str]:
    if not isinstance(payload, Mapping):
        return None
    feedback = payload.get("promptFeedback") or payload.get("prompt_feedback")
    if isinstance(feedback, Mapping):
        block_reason = feedback.get("blockReason") or feedback.get("block_reason")
        if block_reason:
            return _normalize_token(block_reason)
        ratings = feedback.get("safetyRatings") or feedback.get("safety_ratings")
        if isinstance(ratings, list) and any(
            isinstance(item, Mapping)
            and (
                item.get("blocked") is True
                or _normalize_token(item.get("probability")) in {"high", "medium"}
            )
            for item in ratings
        ):
            return "safety"

    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            reason = _normalize_token(
                candidate.get("finishReason") or candidate.get("finish_reason")
            )
            if reason and _contains_any(reason, MODERATION_TOKENS):
                return reason
            ratings = candidate.get("safetyRatings") or candidate.get("safety_ratings")
            if isinstance(ratings, list) and any(
                isinstance(item, Mapping) and item.get("blocked") is True
                for item in ratings
            ):
                return "safety"
    return None


def _classified_error(
    category: str,
    *,
    retryable: bool,
    status: Optional[int],
    code: Optional[str] = None,
) -> ImageGenerationError:
    return ImageGenerationError(
        category,
        SAFE_MESSAGES[category],
        retryable=retryable,
        provider_status=status,
        internal_code=code or None,
    )


def classify_provider_response(
    provider: str,
    status: int,
    payload: Any,
    *,
    has_image: Optional[bool] = None,
) -> Optional[ImageGenerationError]:
    """按业务语义优先、HTTP 状态其次分类供应商响应。"""
    provider_name = _normalize_token(provider)
    if provider_name == "gemini":
        moderation = _gemini_moderation_signal(payload)
        if moderation:
            return _classified_error(
                "moderation", retryable=False, status=status, code=moderation
            )

    raw_error = _extract_provider_error(provider_name, payload)
    code, message = _error_fields(raw_error)
    combined = "_".join(part for part in (code, message) if part)

    if combined:
        if _contains_any(combined, MODERATION_TOKENS):
            return _classified_error(
                "moderation", retryable=False, status=status, code=code
            )
        if _contains_any(combined, QUOTA_TOKENS):
            return _classified_error("quota", retryable=False, status=status, code=code)
        if _contains_any(combined, AUTH_TOKENS):
            return _classified_error("auth", retryable=False, status=status, code=code)
        if _contains_any(combined, INVALID_REQUEST_TOKENS):
            return _classified_error(
                "invalid_request", retryable=False, status=status, code=code
            )
        if _contains_any(combined, RATE_LIMIT_TOKENS):
            return _classified_error(
                "rate_limit", retryable=True, status=status, code=code
            )
        if _contains_any(combined, SERVER_ERROR_TOKENS):
            return _classified_error(
                "server_error", retryable=True, status=status, code=code
            )
        return _classified_error(
            "provider_error", retryable=False, status=status, code=code
        )

    if status in {401, 403}:
        return _classified_error("auth", retryable=False, status=status)
    if status == 429:
        return _classified_error("rate_limit", retryable=True, status=status)
    if status in {500, 502, 503, 504}:
        return _classified_error("server_error", retryable=True, status=status)
    if status >= 400:
        category = "invalid_request" if 400 <= status < 500 else "provider_error"
        return _classified_error(category, retryable=False, status=status)
    if has_image is False:
        return _classified_error("empty_result", retryable=True, status=status)
    return None


def provider_request_error(exc: BaseException) -> ImageGenerationError:
    """把传输异常转换为安全错误；取消必须原样传播。"""
    if isinstance(exc, asyncio.CancelledError):
        raise exc
    if isinstance(exc, httpx.TimeoutException):
        return _classified_error("timeout", retryable=True, status=None)
    if isinstance(exc, httpx.TransportError):
        return _classified_error("connection", retryable=True, status=None)
    return _classified_error("provider_error", retryable=False, status=None)


def classify_download_response(
    *,
    status: int,
    content_type: str,
    content: bytes,
    max_bytes: int = 20 * 1024 * 1024,
) -> Optional[ImageGenerationError]:
    """验证远程图片下载结果，不保留响应体。"""
    if status != 200:
        return _classified_error(
            "download_error",
            retryable=status in RETRYABLE_DOWNLOAD_STATUSES,
            status=status,
        )
    if not (content_type or "").lower().startswith("image/"):
        return _classified_error("invalid_image", retryable=True, status=status)
    if not content or len(content) > max_bytes:
        return _classified_error("invalid_image", retryable=True, status=status)
    try:
        from PIL import Image

        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except Exception:
        return _classified_error("invalid_image", retryable=True, status=status)
    return None


def decode_inline_image(image_data: str) -> bytes:
    """严格解码内联图片，失败视为可降级的供应商无效结果。"""
    encoded = image_data.partition(",")[2] if image_data.startswith("data:") else image_data
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise _classified_error(
            "invalid_image", retryable=True, status=200
        ) from exc
    if not decoded:
        raise _classified_error("invalid_image", retryable=True, status=200)
    validation_error = classify_download_response(
        status=200,
        content_type="image/inline",
        content=decoded,
    )
    if validation_error:
        raise validation_error
    return decoded
