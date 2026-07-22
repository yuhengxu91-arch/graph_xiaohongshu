import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1 import prompt as prompt_api
from app.services.poster_prompt_analyzer import PosterAnalysisError, PosterAnalysisResult


def valid_result():
    return PosterAnalysisResult(
        is_poster=True,
        poster_type="喜报",
        recognized_text=["喜报"],
        layout_description="顶部主标题",
        color_palette=["#FF0000"],
        typography=["粗体"],
        visual_style=["孟菲斯"],
        generation_prompt="生成一张喜报海报",
        negative_prompt="模糊",
        aspect_ratio="3:4",
    )


class ReverseAnalyzeRequestTests(unittest.TestCase):
    def test_rejects_empty_non_string_and_over_14mb_input(self):
        request_model = prompt_api.ReverseAnalyzeRequest
        for value in ("", 123, "x" * (14 * 1024 * 1024 + 1)):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValidationError):
                    request_model.model_validate({"image_base64": value})

    def test_static_reverse_route_is_registered_before_dynamic_prompt_routes(self):
        paths = [route.path for route in prompt_api.router.routes]
        reverse_index = paths.index("/prompts/reverse-analyze")
        first_dynamic_index = min(
            index for index, path in enumerate(paths) if "{prompt_id}" in path
        )
        self.assertLess(reverse_index, first_dynamic_index)


class ReverseAnalyzeAuthenticationTests(unittest.TestCase):
    def test_missing_bearer_token_returns_401(self):
        app = FastAPI()
        app.include_router(prompt_api.router)

        response = TestClient(app).post(
            "/prompts/reverse-analyze",
            json={"image_base64": "data:image/png;base64,AAAA"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "无效的认证凭证")


class ReverseAnalyzeApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_passes_authenticated_user_and_image_to_analyzer(self):
        user_id = uuid4()
        request = SimpleNamespace(image_base64="data:image/png;base64,AAAA")
        analyzer = AsyncMock(return_value=valid_result())

        with patch.object(prompt_api.poster_prompt_analyzer, "analyze", analyzer):
            response = await prompt_api.reverse_analyze_prompt(
                request,
                current_user=SimpleNamespace(id=user_id),
            )

        self.assertEqual(response["poster_type"], "喜报")
        analyzer.assert_awaited_once_with(str(user_id), request.image_base64)

    async def test_maps_service_errors_to_stable_http_contract(self):
        cases = [
            ("MODEL_NOT_CONFIGURED", 503, None),
            ("INVALID_IMAGE", 400, None),
            ("UPSTREAM_AUTH_FAILED", 502, None),
            ("UPSTREAM_RATE_LIMITED", 429, "30"),
            ("CONTENT_REJECTED", 422, None),
            ("ANALYSIS_TIMEOUT", 504, None),
            ("UPSTREAM_INVALID_RESPONSE", 502, None),
            ("UPSTREAM_ERROR", 502, None),
            ("ANALYSIS_RATE_LIMITED", 429, "12"),
        ]
        for code, status_code, retry_after in cases:
            error = PosterAnalysisError(
                code,
                "安全文案",
                status_code=status_code,
                retry_after=retry_after,
            )
            with patch.object(
                prompt_api.poster_prompt_analyzer,
                "analyze",
                AsyncMock(side_effect=error),
            ):
                with self.assertRaises(prompt_api.HTTPException) as ctx:
                    await prompt_api.reverse_analyze_prompt(
                        SimpleNamespace(image_base64="data:image/png;base64,AAAA"),
                        current_user=SimpleNamespace(id=uuid4()),
                    )
            self.assertEqual(ctx.exception.status_code, status_code)
            self.assertEqual(
                ctx.exception.detail,
                {"code": code, "message": "安全文案"},
            )
            expected_headers = {"Retry-After": retry_after} if retry_after else None
            self.assertEqual(ctx.exception.headers, expected_headers)


if __name__ == "__main__":
    unittest.main()
