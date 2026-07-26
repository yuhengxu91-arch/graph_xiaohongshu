import base64
import asyncio
import importlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx

from app.services.poster_service import PosterService
from app.services.image_fallback_service import (
    GenerationContext,
    GenerationOutcome,
    ImageFallbackService,
    ImageModelRef,
)
from app.services.image_generation_errors import ImageGenerationError

poster_service_module = importlib.import_module("app.services.poster_service")
VALID_IMAGE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0l"
    "EQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
VALID_IMAGE_BYTES = base64.b64decode(VALID_IMAGE_B64)


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200, headers=None):
        self._payload = payload if payload is not None else {}
        self.content = content
        self.status_code = status_code
        self.headers = headers or ({"content-type": "image/png"} if content else {})

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://provider.invalid/images")
            response = httpx.Response(
                self.status_code,
                request=request,
                json=self._payload,
            )
            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=request,
                response=response,
            )
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, *, post_response, get_response=None):
        self.post_response = post_response
        self.get_response = get_response
        self.post_payload = None
        self.post_kwargs = None
        self.post_url = None
        self.get_urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        self.post_url = url
        self.post_kwargs = kwargs
        self.post_payload = kwargs.get("json") or kwargs.get("data")
        return self.post_response

    async def get(self, url, timeout=None):
        self.get_urls.append(url)
        return self.get_response


class PosterServiceDoubaoTests(unittest.IsolatedAsyncioTestCase):
    async def test_doubao_accepts_nested_official_response_with_base64(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse(
                {
                    "code": 200,
                    "message": "success",
                    "data": {
                        "model": "doubao-seedream-4-5-251128",
                        "data": [{"b64_json": VALID_IMAGE_B64}],
                    },
                }
            )
        )

        with patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_BASE_URL": "https://example.test/api/v3"}):
            with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
                image = await service._call_doubao_image_api("生成一张海报")

        self.assertEqual(image, VALID_IMAGE_B64)
        self.assertEqual(client.post_payload["response_format"], "b64_json")
        self.assertEqual(client.post_payload["size"], "1536x2048")
        self.assertEqual(client.get_urls, [])

    async def test_doubao_uses_selected_aspect_ratio_size(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"b64_json": VALID_IMAGE_B64}]}),
        )

        with patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_BASE_URL": "https://example.test/api/v3"}):
            with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
                image = await service._call_doubao_image_api("生成一张海报", aspect_ratio="9:16")

        self.assertEqual(image, VALID_IMAGE_B64)
        self.assertEqual(client.post_payload["size"], "1024x1792")

    async def test_call_ai_image_api_passes_aspect_ratio_to_openai_image(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"b64_json": VALID_IMAGE_B64}]}),
        )
        image_model_config = {
            "provider_type": "openai_image",
            "base_url": "https://third-party.example.test",
            "model_name": "nano-banana-pro",
            "api_key": "third-party-key",
            "name": "第三方生图",
        }

        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            image = await service._call_ai_image_api(
                "模板提示词",
                image_model_config=image_model_config,
                aspect_ratio="3:4",
            )

        self.assertEqual(image, VALID_IMAGE_B64)
        self.assertEqual(client.post_payload["size"], "1536x2048")

    async def test_dynamic_openai_image_does_not_log_base_url_or_api_key(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"b64_json": VALID_IMAGE_B64}]}),
        )
        image_model_config = {
            "provider_type": "openai_image",
            "base_url": "https://private-provider.example.test",
            "model_name": "private-model",
            "api_key": "secret-value",
            "name": "私有生图",
        }

        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            with patch("builtins.print") as print_mock:
                await service._call_ai_image_api(
                    "模板提示词",
                    image_model_config=image_model_config,
                )

        log_output = " ".join(str(call) for call in print_mock.call_args_list)
        self.assertNotIn("private-provider.example.test", log_output)
        self.assertNotIn("secret-value", log_output)

    async def test_call_ai_image_api_passes_aspect_ratio_to_doubao(self):
        service = PosterService()
        service.provider = "doubao"
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"b64_json": VALID_IMAGE_B64}]}),
        )

        with patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_BASE_URL": "https://example.test/api/v3"}):
            with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
                image = await service._call_ai_image_api(
                    "模板提示词",
                    aspect_ratio="3:4",
                )

        self.assertEqual(image, VALID_IMAGE_B64)
        self.assertEqual(client.post_payload["size"], "1536x2048")

    async def test_db_template_generation_passes_selected_aspect_ratio_to_image_api(self):
        service = PosterService()

        with patch.object(service, "_call_ai_image_api", AsyncMock(return_value=base64.b64encode(b"png").decode("utf-8"))) as call_mock:
            with patch.object(service, "_save_image", return_value="/static/generated.png"):
                result = await service.generate_from_db_template(
                    template_config={"ai_prompt_template": "生成{title}海报", "default_aspect_ratio": "3:4"},
                    template_name="喜报",
                    template_style_tag=None,
                    params={"title": "本科"},
                    aspect_ratio="3:4",
                )

        self.assertTrue(result["success"])
        self.assertEqual(result["aspect_ratio"], "3:4")
        self.assertEqual(result["width"], 1080)
        self.assertEqual(result["height"], 1440)
        self.assertEqual(call_mock.await_args.kwargs["aspect_ratio"], "3:4")

    async def test_doubao_downloads_url_when_only_url_is_returned(self):
        service = PosterService()
        raw_image = VALID_IMAGE_BYTES
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"url": "https://cdn.example.test/image.png"}]}),
            get_response=FakeResponse(content=raw_image),
        )

        with patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_BASE_URL": "https://example.test/api/v3"}):
            with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
                image = await service._call_doubao_image_api("生成一张海报")

        self.assertEqual(image, base64.b64encode(raw_image).decode("utf-8"))
        self.assertEqual(client.get_urls, ["https://cdn.example.test/image.png"])


class PosterServiceGeminiTests(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_accepts_snake_case_inline_data_from_proxy_response(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "ok"},
                                    {
                                        "inline_data": {
                                            "mime_type": "image/png",
                                            "data": VALID_IMAGE_B64,
                                        }
                                    },
                                ]
                            }
                        }
                    ]
                }
            )
        )

        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            image = await service._call_gemini_api("生成一张海报", use_changhuai=True)

        self.assertEqual(image, VALID_IMAGE_B64)


class PosterServiceStructuredErrorTests(unittest.IsolatedAsyncioTestCase):
    def openai_config(self):
        return {
            "provider_type": "openai_image",
            "base_url": "https://private-provider.example.test",
            "model_name": "private-model",
            "api_key": "secret-value",
            "name": "私有生图",
        }

    async def test_openai_temporary_http_error_is_retryable_and_silent(self):
        client = FakeAsyncClient(
            post_response=FakeResponse(
                {"error": {"code": "service_unavailable", "message": "raw-secret-body"}},
                status_code=503,
            )
        )
        service = PosterService()
        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            with patch("builtins.print") as print_mock:
                with self.assertRaises(ImageGenerationError) as raised:
                    await service._call_openai_image_api(
                        "完整敏感提示词",
                        self.openai_config(),
                    )

        self.assertTrue(raised.exception.retryable)
        self.assertEqual(raised.exception.category, "server_error")
        output = " ".join(str(call) for call in print_mock.call_args_list)
        for secret in (
            "private-provider.example.test",
            "secret-value",
            "完整敏感提示词",
            "raw-secret-body",
        ):
            self.assertNotIn(secret, output)

    async def test_openai_auth_error_is_not_retryable(self):
        client = FakeAsyncClient(
            post_response=FakeResponse(
                {"error": {"code": "invalid_api_key"}},
                status_code=401,
            )
        )
        service = PosterService()
        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(ImageGenerationError) as raised:
                await service._call_openai_image_api("prompt", self.openai_config())
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(raised.exception.category, "auth")

    async def test_openai_empty_and_invalid_inline_results_raise_retryable_errors(self):
        service = PosterService()
        for payload, expected in (
            ({"data": []}, "empty_result"),
            ({"data": [{"b64_json": "not-valid-%%%"}]}, "invalid_image"),
        ):
            client = FakeAsyncClient(post_response=FakeResponse(payload))
            with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
                with self.assertRaises(ImageGenerationError) as raised:
                    await service._call_openai_image_api("prompt", self.openai_config())
            self.assertTrue(raised.exception.retryable)
            self.assertEqual(raised.exception.category, expected)

    async def test_invalid_user_input_image_is_not_retryable(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"b64_json": VALID_IMAGE_B64}]})
        )
        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(ImageGenerationError) as raised:
                await service._call_openai_image_api(
                    "prompt",
                    self.openai_config(),
                    input_image_base64="not-valid-%%%",
                )
        self.assertEqual(raised.exception.category, "invalid_request")
        self.assertFalse(raised.exception.retryable)

    async def test_remote_image_download_is_validated(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"url": "https://cdn.invalid/image"}]}),
            get_response=FakeResponse(
                content=b"<html>bad gateway</html>",
                headers={"content-type": "text/html"},
            ),
        )
        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(ImageGenerationError) as raised:
                await service._call_openai_image_api("prompt", self.openai_config())
        self.assertEqual(raised.exception.category, "invalid_image")
        self.assertTrue(raised.exception.retryable)

    async def test_gemini_safety_block_is_not_retryable(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse(
                {"promptFeedback": {"blockReason": "SAFETY"}}
            )
        )
        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(ImageGenerationError) as raised:
                await service._call_gemini_api(
                    "prompt",
                    dynamic_config={
                        "api_key": "secret-value",
                        "base_url": "https://private-provider.example.test",
                        "model_name": "gemini-image",
                    },
                )
        self.assertEqual(raised.exception.category, "moderation")
        self.assertFalse(raised.exception.retryable)

    async def test_doubao_item_error_is_classified(self):
        service = PosterService()
        client = FakeAsyncClient(
            post_response=FakeResponse(
                {"data": [{"error": {"code": "content_policy_violation"}}]}
            )
        )
        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(ImageGenerationError) as raised:
                await service._call_doubao_image_api(
                    "prompt",
                    dynamic_config={
                        "api_key": "secret-value",
                        "base_url": "https://private-provider.example.test",
                        "model_name": "seedream",
                    },
                )
        self.assertEqual(raised.exception.category, "moderation")
        self.assertFalse(raised.exception.retryable)

    async def test_cancelled_error_propagates(self):
        service = PosterService()

        class CancelledClient(FakeAsyncClient):
            async def post(self, url, **kwargs):
                raise asyncio.CancelledError()

        client = CancelledClient(post_response=FakeResponse())
        with patch.object(poster_service_module.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(asyncio.CancelledError):
                await service._call_openai_image_api("prompt", self.openai_config())

    async def test_poster_fallback_entry_passes_generation_inputs(self):
        service = PosterService()
        primary = ImageModelRef(
            source="builtin",
            display_name="豆包 Seedream",
            provider="doubao",
        )
        coordinator = SimpleNamespace(
            generate=AsyncMock(
                return_value=GenerationOutcome(
                    image_base64=VALID_IMAGE_B64,
                    degraded=False,
                    requested_model_name="豆包 Seedream",
                    actual_model_name="豆包 Seedream",
                    fallback_attempts=0,
                )
            )
        )

        outcome = await service.generate_image_with_fallback(
            prompt="prompt",
            primary_ref=primary,
            context=GenerationContext(chain_id="chain"),
            mode="custom",
            reference_images_base64=[VALID_IMAGE_B64, VALID_IMAGE_B64],
            aspect_ratio="3:4",
            fallback_service=coordinator,
        )

        self.assertEqual(outcome.image_base64, VALID_IMAGE_B64)
        kwargs = coordinator.generate.await_args.kwargs
        self.assertEqual(
            kwargs["required_capabilities"],
            {"multiple_references": True, "aspect_ratio": "3:4"},
        )
        with patch.object(
            service,
            "_call_ai_image_api",
            AsyncMock(return_value=VALID_IMAGE_B64),
        ) as adapter:
            await kwargs["invoke"](
                {
                    "provider_override": "doubao",
                    "image_model_config": None,
                }
            )
        self.assertEqual(adapter.await_args.kwargs["provider_override"], "doubao")
        self.assertEqual(
            adapter.await_args.kwargs["input_images_base64"],
            [VALID_IMAGE_B64, VALID_IMAGE_B64],
        )


class PosterServiceProviderTests(unittest.TestCase):
    def test_removed_system_provider_falls_back_to_gemini_on_startup(self):
        with patch.dict(os.environ, {"IMAGE_PROVIDER": "jimeng", "IMAGE_API_KEY": "test-key"}):
            service = PosterService()

        self.assertEqual(service.provider, "gemini")

    def test_unknown_provider_override_falls_back_to_system_provider(self):
        service = PosterService()
        service.provider = "doubao"

        self.assertEqual(service._get_effective_provider("jimeng"), "doubao")
        self.assertEqual(service._get_effective_provider("unknown"), "doubao")


class PosterServiceBrandKitTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_custom_injects_brand_kit_and_saves_with_brand_kit(self):
        service = PosterService()
        service._call_ai_image_api = AsyncMock(return_value=base64.b64encode(b"fake-png").decode("utf-8"))
        service._save_image = MagicMock(return_value="/static/images/posters/branded.png")
        brand_kit = {
            "brand_name": "慢星咖啡",
            "colors": ["#123456", "#F0E6D2"],
            "font_style": "无衬线粗体",
            "tone_prompt": "温柔克制，像精品咖啡师介绍单品豆。",
            "banned_words": ["全网最低"],
            "logo_url": "/static/brand_logos/logo.png",
        }

        result = await service.generate_custom(
            prompt="新品冷萃上市海报",
            brand_kit=brand_kit,
        )

        self.assertTrue(result["success"])
        self.assertIn("慢星咖啡", result["prompt_used"])
        self.assertIn("#123456", result["prompt_used"])
        self.assertIn("温柔克制", result["prompt_used"])
        self.assertIn("全网最低", result["prompt_used"])
        service._save_image.assert_called_once()
        self.assertEqual(service._save_image.call_args.kwargs["brand_kit"], brand_kit)

    async def test_generate_custom_passes_reference_images_to_image_api(self):
        service = PosterService()
        service._call_ai_image_api = AsyncMock(return_value=base64.b64encode(b"fake-png").decode("utf-8"))
        service._save_image = MagicMock(return_value="/static/images/posters/fused.png")

        result = await service.generate_custom(
            prompt="把图1和图2融合成直播海报",
            reference_images=[
                {"name": "图1", "image_base64": "data:image/png;base64,aW1hZ2Ux"},
                {"name": "图2", "image_base64": "data:image/webp;base64,aW1hZ2Uy"},
            ],
        )

        self.assertTrue(result["success"])
        self.assertIn("用户上传了 2 张参考图片", result["prompt_used"])
        self.assertEqual(
            service._call_ai_image_api.call_args.kwargs["input_images_base64"],
            ["data:image/png;base64,aW1hZ2Ux", "data:image/webp;base64,aW1hZ2Uy"],
        )

    async def test_db_template_generation_injects_brand_kit(self):
        service = PosterService()
        service._call_ai_image_api = AsyncMock(return_value=base64.b64encode(b"fake-png").decode("utf-8"))
        service._save_image = MagicMock(return_value="/static/images/posters/template.png")
        brand_kit = {"brand_name": "云舟研习社", "colors": ["#0055FF"]}

        result = await service.generate_from_db_template(
            template_config={
                "ai_prompt_template": "生成一张 {title} 主题海报，配色 {color_desc}。",
                "text_slots": [{"name": "title", "label": "标题", "required": True}],
            },
            template_name="课程海报",
            template_style_tag=None,
            params={"title": "AI 写作课"},
            brand_kit=brand_kit,
        )

        self.assertTrue(result["success"])
        self.assertIn("云舟研习社", result["prompt_used"])
        self.assertIn("#0055FF", result["prompt_used"])
        self.assertEqual(service._save_image.call_args.kwargs["brand_kit"], brand_kit)

    async def test_save_image_overlays_brand_logo_when_logo_url_exists(self):
        from PIL import Image

        service = PosterService()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service.project_root = root
            service.output_dir = root / "static" / "images" / "posters"
            service.output_dir.mkdir(parents=True)
            logo_dir = root / "static" / "brand_logos"
            logo_dir.mkdir(parents=True)

            base = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
            base_io = io.BytesIO()
            base.save(base_io, format="PNG")
            base_b64 = base64.b64encode(base_io.getvalue()).decode("utf-8")

            logo = Image.new("RGBA", (40, 20), (255, 0, 0, 255))
            logo.save(logo_dir / "logo.png")

            image_url = service._save_image(
                base_b64,
                prefix="brand_test",
                brand_kit={"logo_url": "/static/brand_logos/logo.png"},
            )

            saved = Image.open(root / image_url.lstrip("/")).convert("RGBA")
            self.assertEqual(saved.getpixel((180, 180)), (255, 0, 0, 255))


class PosterApiBrandKitTests(unittest.IsolatedAsyncioTestCase):
    async def test_custom_generation_passes_current_user_brand_kit_to_service(self):
        from app.api.v1 import poster as poster_api

        brand_kit = SimpleNamespace(brand_name="慢星咖啡")
        response_payload = {
            "success": True,
            "image_url": "/static/images/posters/branded.png",
            "prompt_used": "branded prompt",
            "aspect_ratio": "3:4",
            "width": 1080,
            "height": 1440,
            "mode": "custom",
        }
        with patch.object(
            poster_api,
            "_prepare_sync_generation",
            AsyncMock(return_value={
                "user_id": None,
                "brand_kit": brand_kit,
                "model_runtime": {
                    "provider_override": None,
                    "image_model_config": None,
                },
            }),
        ):
            with patch.object(poster_api, "_auto_save_generation", AsyncMock()):
                with patch.object(poster_api.poster_service, "generate_custom", AsyncMock(return_value=response_payload)) as generate_mock:
                    await poster_api.generate_custom(
                        poster_api.CustomGenerateRequest(prompt="新品海报"),
                        current_user=SimpleNamespace(id=uuid4()),
                        db=object(),
                    )

        self.assertIs(generate_mock.call_args.kwargs["brand_kit"], brand_kit)

    async def test_custom_generation_passes_reference_images_without_saving_base64_payload(self):
        from app.api.v1 import poster as poster_api

        response_payload = {
            "success": True,
            "image_url": "/static/images/posters/fused.png",
            "prompt_used": "fused prompt",
            "aspect_ratio": "3:4",
            "width": 1080,
            "height": 1440,
            "mode": "custom",
        }
        saved_payloads = []

        async def capture_generation_record(**kwargs):
            saved_payloads.append(kwargs["request_payload"])

        request = poster_api.CustomGenerateRequest(
            prompt="把图1和图2融合成直播海报",
            reference_images=[
                poster_api.ReferenceImageInput(name="图1", image_base64="data:image/png;base64,aW1hZ2Ux"),
                poster_api.ReferenceImageInput(name="图2", image_base64="data:image/png;base64,aW1hZ2Uy"),
            ],
        )

        with patch.object(
            poster_api,
            "_prepare_sync_generation",
            AsyncMock(return_value={
                "user_id": None,
                "brand_kit": None,
                "model_runtime": {
                    "provider_override": None,
                    "image_model_config": None,
                },
            }),
        ):
            with patch.object(poster_api, "_auto_save_generation", AsyncMock(side_effect=capture_generation_record)):
                with patch.object(poster_api.poster_service, "generate_custom", AsyncMock(return_value=response_payload)) as generate_mock:
                    await poster_api.generate_custom(
                        request,
                        current_user=SimpleNamespace(id=uuid4()),
                        db=object(),
                    )

        self.assertEqual(len(generate_mock.call_args.kwargs["reference_images"]), 2)
        self.assertEqual(
            generate_mock.call_args.kwargs["reference_images"][0]["image_base64"],
            "data:image/png;base64,aW1hZ2Ux",
        )
        self.assertEqual(
            saved_payloads[0]["reference_images"],
            [{"name": "图1", "has_image": True}, {"name": "图2", "has_image": True}],
        )
        self.assertNotIn("aW1hZ2Ux", str(saved_payloads[0]))


class PosterApiSafeModelReferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_removed_provider_uses_system_default_in_sync_generation(self):
        from app.api.v1 import poster as poster_api

        values = iter(["jimeng", None])

        async def execute(statement):
            return SimpleNamespace(scalar_one_or_none=lambda: next(values))

        db = SimpleNamespace(execute=AsyncMock(side_effect=execute), rollback=AsyncMock())
        resolved_refs = []

        async def resolve(model_ref):
            resolved_refs.append(model_ref)
            return {
                "provider_override": model_ref.provider,
                "image_model_config": None,
            }

        with patch.object(poster_api, "_get_user_brand_kit", AsyncMock(return_value=None)):
            with patch.object(
                poster_api.image_model_service,
                "get_default_config",
                AsyncMock(return_value=None),
            ):
                with patch.object(
                    poster_api,
                    "_resolve_model_runtime",
                    AsyncMock(side_effect=resolve),
                ):
                    await poster_api._prepare_sync_generation(
                        db,
                        SimpleNamespace(id=uuid4()),
                    )

        self.assertEqual(resolved_refs[0].provider, poster_api.poster_service.provider)

    async def test_selected_public_model_resolves_safe_reference_before_generation(self):
        from app.api.v1 import poster as poster_api

        config_id = uuid4()
        model_ref = ImageModelRef(
            source="config",
            display_name="公共模型",
            config_id=config_id,
        )
        runtime = {
            "provider_override": None,
            "image_model_config": {
                "provider_type": "openai_image",
                "api_key": "secret-value",
                "base_url": "https://images.example.test",
                "model_name": "gpt-image-2",
            },
        }
        response = {
            "success": True,
            "image_url": "/static/public.png",
            "prompt_used": "p",
            "aspect_ratio": "3:4",
            "width": 1080,
            "height": 1440,
            "mode": "custom",
        }

        with patch.object(poster_api, "_get_user_provider", AsyncMock(return_value=None)):
            with patch.object(poster_api, "_get_user_model_ref", AsyncMock(return_value=model_ref)):
                with patch.object(poster_api, "_resolve_model_runtime", AsyncMock(return_value=runtime)):
                    with patch.object(poster_api, "_get_user_brand_kit", AsyncMock(return_value=None)):
                        with patch.object(poster_api, "_auto_save_generation", AsyncMock()):
                            with patch.object(
                                poster_api.poster_service,
                                "generate_custom",
                                AsyncMock(return_value=response),
                            ) as generate:
                                await poster_api.generate_custom(
                                    poster_api.CustomGenerateRequest(prompt="测试"),
                                    current_user=SimpleNamespace(id=uuid4()),
                                    db=ObservableRequestSession(),
                                )

        self.assertEqual(generate.await_args.kwargs["image_model_config"]["api_key"], "secret-value")
        self.assertIsNone(generate.await_args.kwargs["provider_override"])

    async def test_builtin_model_uses_provider_without_runtime_secret(self):
        from app.api.v1 import poster as poster_api

        model_ref = ImageModelRef(
            source="builtin",
            display_name="豆包 Seedream",
            provider="doubao",
        )
        runtime = {"provider_override": "doubao", "image_model_config": None}
        response = {
            "success": True,
            "image_url": "/static/builtin.png",
            "prompt_used": "p",
            "aspect_ratio": "3:4",
            "width": 1080,
            "height": 1440,
            "mode": "custom",
        }

        with patch.object(poster_api, "_get_user_provider", AsyncMock(return_value=None)):
            with patch.object(poster_api, "_get_user_model_ref", AsyncMock(return_value=model_ref)):
                with patch.object(poster_api, "_resolve_model_runtime", AsyncMock(return_value=runtime)):
                    with patch.object(poster_api, "_get_user_brand_kit", AsyncMock(return_value=None)):
                        with patch.object(poster_api, "_auto_save_generation", AsyncMock()):
                            with patch.object(
                                poster_api.poster_service,
                                "generate_custom",
                                AsyncMock(return_value=response),
                            ) as generate:
                                await poster_api.generate_custom(
                                    poster_api.CustomGenerateRequest(prompt="测试"),
                                    current_user=SimpleNamespace(id=uuid4()),
                                    db=ObservableRequestSession(),
                                )

        self.assertEqual(generate.await_args.kwargs["provider_override"], "doubao")
        self.assertIsNone(generate.await_args.kwargs["image_model_config"])

    async def test_system_default_is_materialized_as_actual_safe_reference(self):
        from app.api.v1 import poster as poster_api

        default_config = SimpleNamespace(id=uuid4(), name="系统公共默认")
        with patch.object(
            poster_api.image_model_service,
            "get_default_config",
            AsyncMock(return_value=default_config),
        ):
            model_ref = await poster_api._get_user_model_ref(
                object(),
                user=None,
                provider=None,
            )

        self.assertEqual(model_ref.source, "config")
        self.assertEqual(model_ref.config_id, default_config.id)
        self.assertNotIn("api_key", model_ref.to_dict())

    async def test_system_default_reference_is_resolved_for_generation(self):
        from app.api.v1 import poster as poster_api

        default_config = SimpleNamespace(id=uuid4(), name="系统公共默认")
        runtime = {
            "provider_override": None,
            "image_model_config": {
                "provider_type": "openai_image",
                "api_key": "runtime-only-secret",
                "base_url": "https://images.example.test",
                "model_name": "gpt-image-2",
            },
        }
        response = {
            "success": True,
            "image_url": "/static/default.png",
            "prompt_used": "p",
            "aspect_ratio": "3:4",
            "width": 1080,
            "height": 1440,
            "mode": "custom",
        }

        with patch.object(poster_api, "_get_user_provider", AsyncMock(return_value=None)):
            with patch.object(
                poster_api.image_model_service,
                "get_default_config",
                AsyncMock(return_value=default_config),
            ):
                with patch.object(
                    poster_api,
                    "_resolve_model_runtime",
                    AsyncMock(return_value=runtime),
                ) as resolve:
                    with patch.object(poster_api, "_get_user_brand_kit", AsyncMock(return_value=None)):
                        with patch.object(poster_api, "_auto_save_generation", AsyncMock()):
                            with patch.object(
                                poster_api.poster_service,
                                "generate_custom",
                                AsyncMock(return_value=response),
                            ):
                                await poster_api.generate_custom(
                                    poster_api.CustomGenerateRequest(prompt="测试"),
                                    current_user=None,
                                    db=ObservableRequestSession(),
                                )

        resolved_ref = resolve.await_args.args[0]
        self.assertEqual(resolved_ref.source, "config")
        self.assertEqual(resolved_ref.config_id, default_config.id)


class ObservableRequestSession:
    def __init__(self):
        self.transaction_active = True
        self.rollback = AsyncMock(side_effect=self._release)

    async def _release(self):
        self.transaction_active = False


class RealRollbackAsyncSession:
    def __init__(self, sync_session):
        self.sync_session = sync_session
        self.rollback_done = False

    async def rollback(self):
        self.sync_session.rollback()
        self.rollback_done = True


class IndependentSaveSession:
    def __init__(self):
        self.commit = AsyncMock()


class AsyncSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class PosterApiSessionLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sqlalchemy_user_is_not_reloaded_after_request_rollback(self):
        from sqlalchemy import create_engine, event, inspect
        from sqlalchemy.orm import Session

        from app.api.v1 import poster as poster_api
        from app.models.user import User

        engine = create_engine("sqlite:///:memory:")
        User.__table__.create(engine)
        sync_session = Session(engine)
        user = User(username="rollback-user", password_hash="hash")
        sync_session.add(user)
        sync_session.commit()
        expected_user_id = user.id
        request_db = RealRollbackAsyncSession(sync_session)
        save_db = IndependentSaveSession()
        model_ref = ImageModelRef(
            source="builtin",
            display_name="豆包 Seedream",
            provider="doubao",
        )
        response = {
            "success": True,
            "image_url": "/static/custom.png",
            "prompt_used": "p",
            "aspect_ratio": "3:4",
            "width": 1080,
            "height": 1440,
            "mode": "custom",
        }
        saved_user_ids = []

        def reject_request_session_reload(
            connection,
            cursor,
            statement,
            parameters,
            context,
            executemany,
        ):
            if request_db.rollback_done and statement.lstrip().upper().startswith("SELECT"):
                raise AssertionError("生成后不得从请求会话重新加载 current_user")

        async def generate(**kwargs):
            self.assertIn("id", inspect(user).expired_attributes)
            return response

        async def save_generation(db, **kwargs):
            self.assertIs(db, save_db)
            saved_user_ids.append(kwargs["user_id"])

        event.listen(engine, "before_cursor_execute", reject_request_session_reload)
        try:
            with patch.object(poster_api, "_get_user_provider", AsyncMock(return_value=None)):
                with patch.object(poster_api, "_get_user_model_ref", AsyncMock(return_value=model_ref)):
                    with patch.object(poster_api, "_get_user_brand_kit", AsyncMock(return_value=None)):
                        with patch.object(
                            poster_api,
                            "_resolve_model_runtime",
                            AsyncMock(return_value={
                                "provider_override": "doubao",
                                "image_model_config": None,
                            }),
                        ):
                            with patch.object(
                                poster_api.poster_service,
                                "generate_custom",
                                AsyncMock(side_effect=generate),
                            ):
                                with patch.object(
                                    poster_api.gallery_service,
                                    "create_generation_record",
                                    AsyncMock(side_effect=save_generation),
                                ):
                                    with patch.object(
                                        poster_api,
                                        "async_session_factory",
                                        MagicMock(return_value=AsyncSessionContext(save_db)),
                                    ):
                                        await poster_api.generate_custom(
                                            poster_api.CustomGenerateRequest(prompt="测试"),
                                            current_user=user,
                                            db=request_db,
                                        )
        finally:
            event.remove(engine, "before_cursor_execute", reject_request_session_reload)
            sync_session.close()
            engine.dispose()

        self.assertEqual(saved_user_ids, [expected_user_id])

    async def test_public_builtin_and_default_contexts_release_request_transaction_before_resolution(self):
        from app.api.v1 import poster as poster_api

        refs = [
            ImageModelRef(source="config", display_name="公共模型", config_id=uuid4()),
            ImageModelRef(source="builtin", display_name="豆包 Seedream", provider="doubao"),
            ImageModelRef(source="config", display_name="系统默认", config_id=uuid4()),
        ]

        for model_ref in refs:
            with self.subTest(source=model_ref.source, name=model_ref.display_name):
                request_db = ObservableRequestSession()

                async def resolve(ref):
                    self.assertIs(ref, model_ref)
                    self.assertFalse(request_db.transaction_active)
                    return {"provider_override": ref.provider, "image_model_config": None}

                with patch.object(poster_api, "_get_user_provider", AsyncMock(return_value=None)):
                    with patch.object(poster_api, "_get_user_model_ref", AsyncMock(return_value=model_ref)):
                        with patch.object(poster_api, "_get_user_brand_kit", AsyncMock(return_value=None)):
                            with patch.object(poster_api, "_resolve_model_runtime", AsyncMock(side_effect=resolve)):
                                context = await poster_api._prepare_sync_generation(
                                    request_db,
                                    user=None,
                                    include_brand=True,
                                )

                self.assertFalse(request_db.transaction_active)
                request_db.rollback.assert_awaited_once()
                self.assertIn("model_runtime", context)

    async def test_custom_generation_releases_request_session_and_saves_with_independent_session(self):
        from app.api.v1 import poster as poster_api

        request_db = ObservableRequestSession()
        save_db = IndependentSaveSession()
        model_ref = ImageModelRef(
            source="builtin",
            display_name="豆包 Seedream",
            provider="doubao",
        )
        response = {
            "success": True,
            "image_url": "/static/custom.png",
            "prompt_used": "p",
            "aspect_ratio": "3:4",
            "width": 1080,
            "height": 1440,
            "mode": "custom",
        }

        async def generate(**kwargs):
            self.assertFalse(request_db.transaction_active)
            return response

        async def save_generation(db, **kwargs):
            self.assertIs(db, save_db)
            self.assertIsNot(db, request_db)

        with patch.object(poster_api, "_get_user_provider", AsyncMock(return_value=None)):
            with patch.object(poster_api, "_get_user_model_ref", AsyncMock(return_value=model_ref)):
                with patch.object(poster_api, "_get_user_brand_kit", AsyncMock(return_value=None)):
                    with patch.object(
                        poster_api,
                        "_resolve_model_runtime",
                        AsyncMock(return_value={"provider_override": "doubao", "image_model_config": None}),
                    ):
                        with patch.object(
                            poster_api.poster_service,
                            "generate_custom",
                            AsyncMock(side_effect=generate),
                        ):
                            with patch.object(
                                poster_api.gallery_service,
                                "create_generation_record",
                                AsyncMock(side_effect=save_generation),
                            ):
                                with patch.object(
                                    poster_api,
                                    "async_session_factory",
                                    MagicMock(return_value=AsyncSessionContext(save_db)),
                                ):
                                    await poster_api.generate_custom(
                                        poster_api.CustomGenerateRequest(prompt="测试"),
                                        current_user=SimpleNamespace(id=uuid4()),
                                        db=request_db,
                                    )

        save_db.commit.assert_awaited_once()

    async def test_custom_edit_and_template_share_pre_generation_entrypoint(self):
        from app.api.v1 import poster as poster_api
        from app.services import template_service as template_service_module

        context = {
            "user_id": None,
            "brand_kit": None,
            "model_runtime": {
                "provider_override": "doubao",
                "image_model_config": None,
            },
        }
        response = {
            "success": True,
            "image_url": "/static/result.png",
            "prompt_used": "p",
            "aspect_ratio": "3:4",
            "width": 1080,
            "height": 1440,
            "mode": "custom",
        }
        prepare = AsyncMock(return_value=context)
        persist = AsyncMock()

        with patch.object(poster_api, "_prepare_sync_generation", prepare):
            with patch.object(poster_api, "_auto_save_generation", persist):
                with patch.object(poster_api.poster_service, "generate_custom", AsyncMock(return_value=response)):
                    await poster_api.generate_custom(
                        poster_api.CustomGenerateRequest(prompt="测试"),
                        current_user=None,
                        db=object(),
                    )
                with patch.object(poster_api.poster_service, "generate_edit", AsyncMock(return_value=response)):
                    await poster_api.generate_edit(
                        poster_api.EditGenerateRequest(
                            image_base64="AAAA",
                            edit_prompt="测试",
                        ),
                        current_user=None,
                        db=object(),
                    )

                template = SimpleNamespace(
                    id=uuid4(),
                    name="模板",
                    style_tag=None,
                    config={},
                )
                with patch.object(
                    template_service_module.template_service,
                    "get_template",
                    AsyncMock(return_value=template),
                ):
                    with patch.object(
                        poster_api.poster_service,
                        "generate_from_db_template",
                        AsyncMock(return_value=response),
                    ):
                        await poster_api.generate_from_template(
                            poster_api.TemplateGenerateRequest(
                                template_id=str(template.id),
                                params={},
                            ),
                            current_user=None,
                            db=object(),
                        )

        self.assertEqual(prepare.await_count, 3)


if __name__ == "__main__":
    unittest.main()
