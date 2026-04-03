"""
火山引擎 API V4 签名模块
用于即梦 AI 图片生成等 visual API 的 HMAC-SHA256 请求签名。
"""
import json
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _sign(secret_key.encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "request")


async def volcengine_signed_request(
    access_key: str,
    secret_key: str,
    body_params: Dict[str, Any],
    *,
    host: str = "visual.volcengineapi.com",
    region: str = "cn-north-1",
    service: str = "cv",
    action: str = "CVProcess",
    version: str = "2022-08-31",
) -> Dict[str, Any]:
    """
    向火山引擎 Visual API 发送签名请求。

    Returns:
        API 返回的 JSON 字典
    """
    method = "POST"
    canonical_uri = "/"
    canonical_querystring = f"Action={action}&Version={version}"

    t = datetime.now(timezone.utc)
    current_date = t.strftime("%Y%m%dT%H%M%SZ")
    datestamp = t.strftime("%Y%m%d")

    req_body = json.dumps(body_params)
    payload_hash = hashlib.sha256(req_body.encode("utf-8")).hexdigest()
    content_type = "application/json"

    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-content-sha256:{payload_hash}\n"
        f"x-date:{current_date}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"

    canonical_request = "\n".join([
        method, canonical_uri, canonical_querystring,
        canonical_headers, signed_headers, payload_hash,
    ])

    algorithm = "HMAC-SHA256"
    credential_scope = f"{datestamp}/{region}/{service}/request"
    string_to_sign = "\n".join([
        algorithm, current_date, credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    signing_key = _get_signing_key(secret_key, datestamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{algorithm} Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "X-Date": current_date,
        "Authorization": authorization,
        "X-Content-Sha256": payload_hash,
        "Content-Type": content_type,
    }

    url = f"https://{host}?{canonical_querystring}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, content=req_body)
        response.raise_for_status()
        return response.json()
