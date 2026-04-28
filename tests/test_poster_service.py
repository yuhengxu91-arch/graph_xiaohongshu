import base64
import os
import unittest
from unittest.mock import patch

from app.services.poster_service import PosterService


class FakeResponse:
    def __init__(self, payload=None, content=b""):
        self._payload = payload if payload is not None else {}
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, *, post_response, get_response=None):
        self.post_response = post_response
        self.get_response = get_response
        self.post_payload = None
        self.get_urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers):
        self.post_payload = json
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
                        "data": [{"b64_json": "nested-image"}],
                    },
                }
            )
        )

        with patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_BASE_URL": "https://example.test/api/v3"}):
            with patch("app.services.poster_service.httpx.AsyncClient", return_value=client):
                image = await service._call_doubao_image_api("生成一张海报")

        self.assertEqual(image, "nested-image")
        self.assertEqual(client.post_payload["response_format"], "b64_json")
        self.assertEqual(client.get_urls, [])

    async def test_doubao_downloads_url_when_only_url_is_returned(self):
        service = PosterService()
        raw_image = b"fake-png"
        client = FakeAsyncClient(
            post_response=FakeResponse({"data": [{"url": "https://cdn.example.test/image.png"}]}),
            get_response=FakeResponse(content=raw_image),
        )

        with patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_BASE_URL": "https://example.test/api/v3"}):
            with patch("app.services.poster_service.httpx.AsyncClient", return_value=client):
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
                                            "data": "proxy-image",
                                        }
                                    },
                                ]
                            }
                        }
                    ]
                }
            )
        )

        with patch("app.services.poster_service.httpx.AsyncClient", return_value=client):
            image = await service._call_gemini_api("生成一张海报", use_changhuai=True)

        self.assertEqual(image, "proxy-image")


if __name__ == "__main__":
    unittest.main()
