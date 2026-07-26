import asyncio
import base64
import unittest

import httpx

from app.services.image_generation_errors import (
    ImageGenerationError,
    classify_download_response,
    classify_provider_response,
    decode_inline_image,
    provider_request_error,
)

VALID_IMAGE_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0l"
    "EQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class ProviderErrorClassificationTests(unittest.TestCase):
    def assert_error(self, error, *, category, retryable):
        self.assertIsInstance(error, ImageGenerationError)
        self.assertEqual(error.category, category)
        self.assertEqual(error.retryable, retryable)

    def test_connection_and_timeout_are_retryable(self):
        request = httpx.Request("POST", "https://provider.invalid/images")
        for exc, category in (
            (httpx.ConnectError("down", request=request), "connection"),
            (httpx.ReadTimeout("slow", request=request), "timeout"),
        ):
            error = provider_request_error(exc)
            self.assert_error(error, category=category, retryable=True)

    def test_cancelled_error_is_not_wrapped(self):
        cancelled = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            provider_request_error(cancelled)

    def test_retryable_http_statuses_are_strict(self):
        for status in (429, 500, 502, 503, 504):
            error = classify_provider_response("openai", status, {})
            self.assertTrue(error.retryable, status)
        for status in (501, 505, 507):
            error = classify_provider_response("openai", status, {})
            self.assertFalse(error.retryable, status)

    def test_auth_invalid_request_and_unknown_errors_are_not_retryable(self):
        cases = (
            (401, {"error": {"code": "invalid_api_key"}}, "auth"),
            (403, {"error": {"message": "Unauthorized API key"}}, "auth"),
            (400, {"error": {"code": "invalid-size"}}, "invalid_request"),
            (418, {"error": {"code": "unknown-provider-problem"}}, "provider_error"),
        )
        for status, payload, category in cases:
            error = classify_provider_response("openai", status, payload)
            self.assert_error(error, category=category, retryable=False)

    def test_business_quota_and_moderation_override_http_429(self):
        quota = classify_provider_response(
            "openai",
            429,
            {"error": {"code": "INSUFFICIENT_QUOTA", "message": "Balance exhausted"}},
        )
        moderation = classify_provider_response(
            "gemini",
            429,
            {"error": {"code": "PROHIBITED-CONTENT", "message": "blocked by safety policy"}},
        )
        self.assert_error(quota, category="quota", retryable=False)
        self.assert_error(moderation, category="moderation", retryable=False)

    def test_error_codes_are_normalized(self):
        for code in ("rate-limit-exceeded", "RATE_LIMIT_EXCEEDED", "RateLimitExceeded"):
            error = classify_provider_response(
                "openai",
                200,
                {"error": {"code": code, "message": "temporary throttling"}},
            )
            self.assert_error(error, category="rate_limit", retryable=True)

    def test_http_200_root_error_uses_error_table(self):
        error = classify_provider_response(
            "openai",
            200,
            {"error": {"code": "server_error", "message": "temporarily unavailable"}},
        )
        self.assert_error(error, category="server_error", retryable=True)

    def test_gemini_safety_signals_are_not_empty_results(self):
        payloads = (
            {"promptFeedback": {"blockReason": "SAFETY"}},
            {"promptFeedback": {"safetyRatings": [{"blocked": True}]}},
            {"candidates": [{"finishReason": "PROHIBITED_CONTENT"}]},
            {"candidates": [{"finishReason": "BLOCKLIST"}]},
            {"candidates": [{"finishReason": "SPII"}]},
            {"candidates": [{"finishReason": "IMAGE_SAFETY"}]},
        )
        for payload in payloads:
            error = classify_provider_response("gemini", 200, payload, has_image=False)
            self.assert_error(error, category="moderation", retryable=False)

    def test_gemini_stop_without_image_is_retryable_empty_result(self):
        error = classify_provider_response(
            "gemini",
            200,
            {"candidates": [{"finishReason": "STOP"}]},
            has_image=False,
        )
        self.assert_error(error, category="empty_result", retryable=True)

    def test_doubao_nested_errors_follow_root_data_item_priority(self):
        root = classify_provider_response(
            "doubao",
            200,
            {
                "error": {"code": "invalid_api_key"},
                "data": {"error": {"code": "server_error"}},
            },
        )
        nested = classify_provider_response(
            "doubao",
            200,
            {"data": {"error": {"code": "service_unavailable"}}},
        )
        item = classify_provider_response(
            "doubao",
            200,
            {"data": [{"error": {"code": "content_policy_violation"}}]},
        )
        self.assert_error(root, category="auth", retryable=False)
        self.assert_error(nested, category="server_error", retryable=True)
        self.assert_error(item, category="moderation", retryable=False)

    def test_success_without_image_is_retryable_empty_result(self):
        error = classify_provider_response("openai", 200, {"data": []}, has_image=False)
        self.assert_error(error, category="empty_result", retryable=True)


class ImagePayloadValidationTests(unittest.TestCase):
    def test_inline_base64_must_decode(self):
        with self.assertRaises(ImageGenerationError) as raised:
            decode_inline_image("not-valid-%%%")
        self.assert_error(raised.exception, category="invalid_image", retryable=True)

    def assert_error(self, error, *, category, retryable):
        self.assertEqual(error.category, category)
        self.assertEqual(error.retryable, retryable)

    def test_download_status_classification(self):
        for status in (404, 408, 429, 500, 502, 503, 504):
            error = classify_download_response(
                status=status,
                content_type="image/png",
                content=VALID_IMAGE_BYTES,
            )
            self.assert_error(error, category="download_error", retryable=True)
        for status in (400, 401, 403, 422):
            error = classify_download_response(
                status=status,
                content_type="image/png",
                content=VALID_IMAGE_BYTES,
            )
            self.assert_error(error, category="download_error", retryable=False)

    def test_download_rejects_non_image_and_oversized_payload(self):
        non_image = classify_download_response(
            status=200,
            content_type="text/html",
            content=b"<html></html>",
        )
        oversized = classify_download_response(
            status=200,
            content_type="image/png",
            content=b"x" * 11,
            max_bytes=10,
        )
        self.assert_error(non_image, category="invalid_image", retryable=True)
        self.assert_error(oversized, category="invalid_image", retryable=True)

    def test_download_rejects_corrupt_image_bytes(self):
        error = classify_download_response(
            status=200,
            content_type="image/png",
            content=b"not-an-image",
        )
        self.assert_error(error, category="invalid_image", retryable=True)

    def test_valid_download_returns_none(self):
        self.assertIsNone(
            classify_download_response(
                status=200,
                content_type="image/png",
                content=VALID_IMAGE_BYTES,
            )
        )


if __name__ == "__main__":
    unittest.main()
