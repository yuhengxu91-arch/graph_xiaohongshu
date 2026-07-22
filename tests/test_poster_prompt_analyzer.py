import base64
import asyncio
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image, PngImagePlugin
from pydantic import ValidationError

from app.services.poster_prompt_analyzer import (
    PosterAnalysisError,
    PosterAnalysisResult,
    InMemoryUserAnalysisLimiter,
    PosterPromptAnalyzer,
)


def image_data_url(
    image: Image.Image,
    *,
    image_format: str = "PNG",
    declared_mime: str | None = None,
    **save_options,
) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format=image_format, **save_options)
    mime = declared_mime or {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
    }[image_format]
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


class PosterAnalysisResultTests(unittest.TestCase):
    def valid_result(self, **overrides):
        data = {
            "is_poster": True,
            "poster_type": "喜报",
            "recognized_text": ["喜报", "20k offer"],
            "layout_description": "顶部主标题，中部信息区",
            "color_palette": ["#F43F5E", "#2563EB"],
            "typography": ["粗体立体标题"],
            "visual_style": ["孟菲斯"],
            "generation_prompt": "生成一张高饱和孟菲斯喜报海报",
            "negative_prompt": "模糊文字",
            "aspect_ratio": "3:4",
        }
        data.update(overrides)
        return data

    def test_accepts_complete_poster_result(self):
        result = PosterAnalysisResult.model_validate(self.valid_result())
        self.assertTrue(result.is_poster)

    def test_rejects_extra_fields_and_invalid_color_or_ratio(self):
        with self.assertRaises(ValidationError):
            PosterAnalysisResult.model_validate(self.valid_result(extra="no"))
        with self.assertRaises(ValidationError):
            PosterAnalysisResult.model_validate(
                self.valid_result(color_palette=["red"])
            )
        with self.assertRaises(ValidationError):
            PosterAnalysisResult.model_validate(
                self.valid_result(aspect_ratio="4:5")
            )

    def test_poster_requires_non_blank_generation_prompt(self):
        with self.assertRaises(ValidationError):
            PosterAnalysisResult.model_validate(
                self.valid_result(generation_prompt="   ")
            )

    def test_non_poster_requires_canonical_empty_fields(self):
        result = PosterAnalysisResult.model_validate(
            {
                "is_poster": False,
                "poster_type": "",
                "recognized_text": [],
                "layout_description": "",
                "color_palette": [],
                "typography": [],
                "visual_style": [],
                "generation_prompt": "",
                "negative_prompt": "",
                "aspect_ratio": "unknown",
            }
        )
        self.assertFalse(result.is_poster)
        with self.assertRaises(ValidationError):
            PosterAnalysisResult.model_validate(
                self.valid_result(is_poster=False, generation_prompt="still present")
            )


class PosterImageSanitizationTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = PosterPromptAnalyzer()

    def assert_invalid(self, data_url: str):
        with self.assertRaises(PosterAnalysisError) as ctx:
            self.analyzer.sanitize_image(data_url)
        self.assertEqual(ctx.exception.code, "INVALID_IMAGE")

    def test_rejects_malformed_data_url_and_non_strict_base64(self):
        self.assert_invalid("not-a-data-url")
        self.assert_invalid("data:image/png;base64,%%%%")
        self.assert_invalid("data:image/gif;base64,AAAA")

    def test_rejects_encoded_and_decoded_size_limits(self):
        self.analyzer.MAX_ENCODED_LENGTH = 20
        self.assert_invalid("data:image/png;base64," + "A" * 21)

        self.analyzer.MAX_ENCODED_LENGTH = 100
        self.analyzer.MAX_DECODED_BYTES = 3
        self.assert_invalid("data:image/png;base64," + base64.b64encode(b"1234").decode())

    def test_rejects_declared_mime_that_does_not_match_real_format(self):
        source = image_data_url(
            Image.new("RGB", (8, 8), "red"),
            image_format="PNG",
            declared_mime="image/jpeg",
        )
        self.assert_invalid(source)

    def test_rejects_animated_or_multiframe_image(self):
        first = Image.new("RGB", (8, 8), "red")
        second = Image.new("RGB", (8, 8), "blue")
        source = image_data_url(
            first,
            image_format="WEBP",
            save_all=True,
            append_images=[second],
        )
        self.assert_invalid(source)

    def test_rejects_dimension_and_pixel_limits(self):
        source = image_data_url(Image.new("RGB", (20, 20), "red"))
        self.analyzer.MAX_DIMENSION = 10
        self.assert_invalid(source)

        self.analyzer.MAX_DIMENSION = 100
        self.analyzer.MAX_PIXELS = 300
        self.assert_invalid(source)

    def test_composites_transparency_on_white_and_strips_metadata(self):
        image = Image.new("RGBA", (4, 4), (255, 0, 0, 128))
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("private", "must disappear")
        source = image_data_url(image, pnginfo=metadata)

        sanitized = self.analyzer.sanitize_image(source)

        self.assertTrue(sanitized.startswith("data:image/webp;base64,"))
        payload = base64.b64decode(sanitized.split(",", 1)[1])
        with Image.open(io.BytesIO(payload)) as output:
            self.assertEqual(output.format, "WEBP")
            self.assertEqual(output.mode, "RGB")
            red, green, blue = output.getpixel((0, 0))
            self.assertGreater(red, 240)
            self.assertGreater(green, 100)
            self.assertGreater(blue, 100)
            self.assertNotIn("private", output.info)
            self.assertNotIn("exif", output.info)

    def test_shrinks_output_by_twenty_percent_until_it_fits(self):
        source = image_data_url(Image.new("RGB", (100, 50), "red"))
        self.analyzer.MAX_OUTPUT_BYTES = 100
        self.analyzer.MIN_OUTPUT_LONG_EDGE = 10
        seen_sizes = []

        def fake_encode(image):
            seen_sizes.append(image.size)
            return b"x" * (101 if len(seen_sizes) == 1 else 100)

        with patch.object(self.analyzer, "_encode_webp", side_effect=fake_encode):
            result = self.analyzer.sanitize_image(source)

        self.assertEqual(seen_sizes, [(100, 50), (80, 40)])
        self.assertEqual(base64.b64decode(result.split(",", 1)[1]), b"x" * 100)

    def test_rejects_when_output_is_still_too_large_below_minimum_edge(self):
        source = image_data_url(Image.new("RGB", (20, 10), "red"))
        self.analyzer.MAX_OUTPUT_BYTES = 1
        self.analyzer.MIN_OUTPUT_LONG_EDGE = 10
        with patch.object(self.analyzer, "_encode_webp", return_value=b"xx"):
            self.assert_invalid(source)


def valid_analysis_payload(**overrides):
    data = PosterAnalysisResultTests().valid_result(**overrides)
    return data


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class PosterPromptAnalyzerHttpTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.image = image_data_url(Image.new("RGB", (8, 8), "red"))
        self.settings = SimpleNamespace(
            ark_api_key="ark-secret-key",
            ark_vision_model="ep-doubao-seed-2-1-pro",
            ark_base_url="https://ark.example/api/v3/",
            ark_vision_timeout=12.0,
        )

    def make_analyzer(self, outcomes):
        client = FakeAsyncClient(outcomes)
        analyzer = PosterPromptAnalyzer(
            settings_obj=self.settings,
            client_factory=lambda **kwargs: client,
            limiter=InMemoryUserAnalysisLimiter(max_per_hour=100),
        )
        return analyzer, client

    async def test_builds_hardened_responses_payload_and_schema(self):
        analyzer, client = self.make_analyzer(
            [FakeResponse(payload={"output_text": json.dumps(valid_analysis_payload())})]
        )

        await analyzer.analyze(str(uuid4()), self.image)

        url, request = client.requests[0]
        self.assertEqual(url, "https://ark.example/api/v3/responses")
        self.assertEqual(request["headers"]["Authorization"], "Bearer ark-secret-key")
        body = request["json"]
        self.assertEqual(body["model"], "ep-doubao-seed-2-1-pro")
        self.assertFalse(body["store"])
        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertNotIn("tools", body)
        system_text = body["input"][0]["content"][0]["text"]
        self.assertIn("不可信数据", system_text)
        self.assertIn("不得执行", system_text)
        image_url = body["input"][1]["content"][0]["image_url"]
        self.assertTrue(image_url.startswith("data:image/webp;base64,"))
        schema_format = body["text"]["format"]
        self.assertEqual(schema_format["type"], "json_schema")
        self.assertTrue(schema_format["strict"])
        schema = schema_format["schema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(PosterAnalysisResult.model_fields))
        properties = schema["properties"]
        self.assertEqual(properties["recognized_text"]["maxItems"], 50)
        self.assertEqual(properties["recognized_text"]["items"]["maxLength"], 200)
        self.assertEqual(properties["typography"]["items"]["maxLength"], 100)
        self.assertEqual(properties["visual_style"]["items"]["maxLength"], 100)
        self.assertEqual(properties["generation_prompt"]["maxLength"], 4000)
        self.assertEqual(properties["color_palette"]["items"]["pattern"], r"^#[0-9A-Fa-f]{6}$")

    async def test_extracts_nested_output_text(self):
        response = {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": json.dumps(valid_analysis_payload())}
                    ],
                }
            ],
        }
        analyzer, _ = self.make_analyzer([FakeResponse(payload=response)])
        result = await analyzer.analyze(str(uuid4()), self.image)
        self.assertEqual(result.poster_type, "喜报")

    async def test_rejects_empty_non_json_or_schema_invalid_output(self):
        for output in ("", "not-json", json.dumps({"is_poster": True})):
            analyzer, _ = self.make_analyzer([FakeResponse(payload={"output_text": output})])
            with self.assertRaises(PosterAnalysisError) as ctx:
                await analyzer.analyze(str(uuid4()), self.image)
            self.assertEqual(ctx.exception.code, "UPSTREAM_INVALID_RESPONSE")

    async def test_rejects_valid_json_with_unexpected_container_shapes(self):
        malformed_payloads = [[], "text", {"output": [1]}, {"output": [{"content": [1]}]}]
        for payload in malformed_payloads:
            analyzer, _ = self.make_analyzer([FakeResponse(payload=payload)])
            with self.assertRaises(PosterAnalysisError) as ctx:
                await analyzer.analyze(str(uuid4()), self.image)
            self.assertEqual(ctx.exception.code, "UPSTREAM_INVALID_RESPONSE")

    async def test_maps_refusal_and_content_filter_to_content_rejected(self):
        responses = [
            {"output": [{"content": [{"type": "refusal", "refusal": "no"}]}]},
            {"status": "incomplete", "incomplete_details": {"reason": "content_filter"}},
        ]
        for response in responses:
            analyzer, _ = self.make_analyzer([FakeResponse(payload=response)])
            with self.assertRaises(PosterAnalysisError) as ctx:
                await analyzer.analyze(str(uuid4()), self.image)
            self.assertEqual(ctx.exception.code, "CONTENT_REJECTED")
            self.assertEqual(ctx.exception.status_code, 422)

    async def test_requires_both_ark_key_and_model(self):
        for field in ("ark_api_key", "ark_vision_model"):
            settings_obj = SimpleNamespace(**vars(self.settings))
            setattr(settings_obj, field, "")
            analyzer = PosterPromptAnalyzer(settings_obj=settings_obj)
            with self.assertRaises(PosterAnalysisError) as ctx:
                await analyzer.analyze(str(uuid4()), self.image)
            self.assertEqual(ctx.exception.code, "MODEL_NOT_CONFIGURED")
            self.assertEqual(ctx.exception.status_code, 503)

    async def test_maps_auth_rate_limit_and_other_client_errors_without_retry(self):
        cases = [
            (401, "UPSTREAM_AUTH_FAILED", 502, {}),
            (403, "UPSTREAM_AUTH_FAILED", 502, {}),
            (429, "UPSTREAM_RATE_LIMITED", 429, {"Retry-After": "15"}),
            (400, "UPSTREAM_ERROR", 502, {}),
        ]
        for status_code, code, expected_status, headers in cases:
            analyzer, client = self.make_analyzer(
                [FakeResponse(status_code=status_code, headers=headers, text="secret upstream body")]
            )
            with self.assertRaises(PosterAnalysisError) as ctx:
                await analyzer.analyze(str(uuid4()), self.image)
            self.assertEqual(ctx.exception.code, code)
            self.assertEqual(ctx.exception.status_code, expected_status)
            self.assertEqual(len(client.requests), 1)
        self.assertEqual(ctx.exception.retry_after, None)

    async def test_safely_normalizes_retry_after(self):
        for value, expected in (("120", "120"), ("999999", "3600"), ("bad\r\nX: y", None)):
            analyzer, _ = self.make_analyzer(
                [FakeResponse(status_code=429, headers={"Retry-After": value})]
            )
            with self.assertRaises(PosterAnalysisError) as ctx:
                await analyzer.analyze(str(uuid4()), self.image)
            self.assertEqual(ctx.exception.retry_after, expected)

    async def test_retries_connection_and_server_errors_once(self):
        request = httpx.Request("POST", "https://ark.example/api/v3/responses")
        connection_error = httpx.ConnectError("down", request=request)
        success = FakeResponse(payload={"output_text": json.dumps(valid_analysis_payload())})
        for first_failure in (connection_error, FakeResponse(status_code=503)):
            analyzer, client = self.make_analyzer([first_failure, success])
            result = await analyzer.analyze(str(uuid4()), self.image)
            self.assertTrue(result.is_poster)
            self.assertEqual(len(client.requests), 2)

    async def test_maps_timeout_after_retry_policy(self):
        request = httpx.Request("POST", "https://ark.example/api/v3/responses")
        analyzer, client = self.make_analyzer(
            [httpx.ReadTimeout("slow", request=request)]
        )
        with self.assertRaises(PosterAnalysisError) as ctx:
            await analyzer.analyze(str(uuid4()), self.image)
        self.assertEqual(ctx.exception.code, "ANALYSIS_TIMEOUT")
        self.assertEqual(ctx.exception.status_code, 504)
        self.assertEqual(len(client.requests), 1)

    async def test_maps_upstream_moderation_error_to_content_rejected(self):
        analyzer, client = self.make_analyzer(
            [
                FakeResponse(
                    status_code=400,
                    payload={
                        "error": {
                            "code": "content_policy_violation",
                            "message": "upstream detail must stay private",
                        }
                    },
                )
            ]
        )
        with self.assertRaises(PosterAnalysisError) as ctx:
            await analyzer.analyze(str(uuid4()), self.image)
        self.assertEqual(ctx.exception.code, "CONTENT_REJECTED")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(len(client.requests), 1)

    async def test_maps_sensitive_image_error_code_to_content_rejected(self):
        analyzer, _ = self.make_analyzer([
            FakeResponse(
                status_code=400,
                payload={"error": {"code": "InputImageSensitiveContentDetected"}},
            )
        ])
        with self.assertRaises(PosterAnalysisError) as ctx:
            await analyzer.analyze(str(uuid4()), self.image)
        self.assertEqual(ctx.exception.code, "CONTENT_REJECTED")
        self.assertEqual(ctx.exception.status_code, 422)

    async def test_invalid_response_logs_request_id_and_safe_error_code(self):
        analyzer, _ = self.make_analyzer([FakeResponse(payload=[])])
        with self.assertLogs("app.services.poster_prompt_analyzer", level="WARNING") as logs:
            with self.assertRaises(PosterAnalysisError):
                await analyzer.analyze(str(uuid4()), self.image)
        combined = "\n".join(logs.output)
        self.assertIn("id=", combined)
        self.assertIn("UPSTREAM_INVALID_RESPONSE", combined)
        self.assertNotIn("data:image", combined)

    async def test_stops_after_one_server_error_retry_and_logs_no_sensitive_data(self):
        analyzer, client = self.make_analyzer(
            [
                FakeResponse(status_code=503, text="secret upstream body"),
                FakeResponse(status_code=503, text="secret upstream body"),
            ]
        )
        with self.assertLogs("app.services.poster_prompt_analyzer", level="WARNING") as logs:
            with self.assertRaises(PosterAnalysisError) as ctx:
                await analyzer.analyze(str(uuid4()), self.image)
        self.assertEqual(ctx.exception.code, "UPSTREAM_ERROR")
        self.assertEqual(len(client.requests), 2)
        combined = "\n".join(logs.output)
        self.assertNotIn("ark-secret-key", combined)
        self.assertNotIn("data:image", combined)
        self.assertNotIn("secret upstream body", combined)

    async def test_cancelled_analysis_releases_user_concurrency_slot(self):
        started = asyncio.Event()

        class BlockingClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, **kwargs):
                started.set()
                await asyncio.Event().wait()

        limiter = InMemoryUserAnalysisLimiter(max_per_hour=10)
        analyzer = PosterPromptAnalyzer(
            settings_obj=self.settings,
            client_factory=lambda **kwargs: BlockingClient(),
            limiter=limiter,
        )
        user_id = str(uuid4())
        task = asyncio.create_task(analyzer.analyze(user_id, self.image))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        await limiter.acquire(user_id)
        await limiter.release(user_id)


class InMemoryUserAnalysisLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_same_user_concurrency_but_allows_other_users(self):
        limiter = InMemoryUserAnalysisLimiter(max_per_hour=10)
        await limiter.acquire("one")
        with self.assertRaises(PosterAnalysisError) as ctx:
            await limiter.acquire("one")
        self.assertEqual(ctx.exception.code, "ANALYSIS_RATE_LIMITED")
        await limiter.acquire("two")
        await limiter.release("two")
        await limiter.release("one")

    async def test_enforces_sliding_hour_and_expires_old_entries(self):
        now = [1000.0]
        limiter = InMemoryUserAnalysisLimiter(
            max_per_hour=2,
            clock=lambda: now[0],
        )
        for _ in range(2):
            await limiter.acquire("one")
            await limiter.release("one")
        with self.assertRaises(PosterAnalysisError) as ctx:
            await limiter.acquire("one")
        self.assertEqual(ctx.exception.retry_after, "3600")
        now[0] += 3601
        await limiter.acquire("one")
        await limiter.release("one")

    async def test_rejected_concurrency_does_not_consume_hourly_quota(self):
        limiter = InMemoryUserAnalysisLimiter(max_per_hour=2)
        await limiter.acquire("one")
        with self.assertRaises(PosterAnalysisError):
            await limiter.acquire("one")
        await limiter.release("one")
        await limiter.acquire("one")
        await limiter.release("one")
        with self.assertRaises(PosterAnalysisError):
            await limiter.acquire("one")


if __name__ == "__main__":
    unittest.main()
