"""
图片生成服务模块
使用 Gemini Image API 生成小红书风格配图
"""
import os
import asyncio
import base64
import uuid
import random
import httpx
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class ImageService:
    """图片生成服务类"""

    SUPPORTED_PROVIDERS = {"gemini", "gemini_ch", "doubao", "gpt_image"}

    XHS_STYLE_PROMPT = """请根据以下内容生成一张小红书风格的爆款配图：

【内容主题】
{content}

【图片要求】
- 风格：小红书流行的高质感、精致感、氛围感风格
- 色调：明亮温暖、柔和治愈、或高级感色调
- 构图：简洁大气、留白得当、视觉重点突出
- 比例：3:4 竖版构图（适合手机浏览）

【风格参考】
- 美食：诱人的食物特写，暖色调打光
- 穿搭：时尚感穿搭展示，简约背景
- 家居：温馨舒适的生活场景，ins风或日系风
- 知识/干货：清新简约的图文排版，扁平插画
- 其他：根据内容匹配最适合的小红书流行风格

请生成一张高质量、有吸引力的图片。"""

    FALLBACK_PROMPTS = [
        "小红书风格，明亮温暖的生活场景，咖啡和书本，柔和自然光，3:4竖版构图",
        "小红书风格，创意工作台，文具和绿植，ins风格，3:4竖版构图",
        "小红书风格，清新简约的扁平插画，渐变色背景，3:4竖版构图",
    ]

    def __init__(self):
        configured_provider = os.getenv("IMAGE_PROVIDER", "gemini").lower()
        self.provider = configured_provider if configured_provider in self.SUPPORTED_PROVIDERS else "gemini"

        # Gemini 代理 1（xunruijie）
        self.api_key = os.getenv("IMAGE_API_KEY", "")
        self.base_url = os.getenv("IMAGE_BASE_URL", "https://api.xunruijie.com")
        self.model = os.getenv("IMAGE_MODEL", "gemini-3-pro-image-preview")

        # Gemini 代理 2（changhuai）
        self.api_key_ch = os.getenv("IMAGE_API_KEY_CH", "")
        self.base_url_ch = os.getenv("IMAGE_BASE_URL_CH", "https://www.changhuai.vip")
        self.model_ch = os.getenv("IMAGE_MODEL_CH", "gemini-3-pro-image-preview")

        # GPT Image 2（scdn）
        self.gpt_image_api_key = os.getenv("GPT_IMAGE_API_KEY", "")
        self.gpt_image_base_url = os.getenv("GPT_IMAGE_BASE_URL", "https://api.scdn.online")
        self.gpt_image_model = os.getenv("GPT_IMAGE_MODEL", "gpt-image-2")

        self.image_dir = Path("static/images/generated")
        self.image_dir.mkdir(parents=True, exist_ok=True)

        active_key = self._get_provider_api_key(self.provider)
        if not active_key:
            print(f"[ImageService] 警告: API Key 未配置（当前引擎: {self.provider}），图片生成功能不可用")

    def _get_effective_provider(self, provider_override: Optional[str] = None) -> str:
        """获取实际使用的引擎，支持用户偏好覆盖"""
        if provider_override and provider_override != "system" and provider_override in self.SUPPORTED_PROVIDERS:
            return provider_override
        return self.provider

    def _get_provider_api_key(self, provider: str) -> str:
        """返回 provider 对应的 API Key，用于启动时配置检查。"""
        if provider == "doubao":
            return os.getenv("LLM_API_KEY", "")
        if provider == "gemini_ch":
            return self.api_key_ch
        if provider == "gpt_image":
            return self.gpt_image_api_key
        return self.api_key

    def _build_api_url(self) -> str:
        return f"{self.base_url}/v1beta/models/{self.model}:generateContent"

    def _save_image(self, image_base64: str, prefix: str = "xhs") -> str:
        """保存 base64 图片到本地"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{prefix}_{timestamp}_{unique_id}.png"
        
        file_path = self.image_dir / filename
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(image_base64))
        
        return f"/static/images/generated/{filename}"

    async def _call_image_api(self, prompt: str, provider_override: Optional[str] = None) -> Optional[str]:
        """根据 provider 分派到对应 API，支持动态覆盖"""
        effective = self._get_effective_provider(provider_override)
        if effective == "doubao":
            return await self._call_doubao_image_api(prompt)
        if effective == "gpt_image":
            return await self._call_gpt_image_api(prompt)
        if effective == "gemini_ch":
            return await self._call_gemini_api(prompt, use_changhuai=True)
        return await self._call_gemini_api(prompt)

    async def _call_doubao_image_api(self, prompt: str) -> Optional[str]:
        """调用火山方舟 doubao-seedream 图片生成 API"""
        import os as _os
        llm_api_key = _os.getenv("LLM_API_KEY", "")
        llm_base_url = _os.getenv("LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        model = _os.getenv("DOUBAO_IMAGE_MODEL", "doubao-seedream-3-0-t2i-250415")

        if not llm_api_key:
            print("[ImageService] LLM_API_KEY 未配置")
            return None

        url = f"{llm_base_url}/images/generations"
        payload = {
            "model": model,
            "prompt": prompt,
            "response_format": "url",
            "size": "2048x2048",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {llm_api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                data_list = result.get("data", [])
                if data_list:
                    item = data_list[0]
                    if item.get("b64_json"):
                        return item["b64_json"]
                    if item.get("url"):
                        img_resp = await client.get(item["url"], timeout=60.0)
                        img_resp.raise_for_status()
                        return base64.b64encode(img_resp.content).decode("utf-8")

                print(f"[ImageService] doubao 生图无图片: {str(result)[:200]}")
                return None
        except httpx.HTTPStatusError as e:
            print(f"[ImageService] doubao 生图错误: {e.response.status_code} {e.response.text[:200]}")
            return None
        except Exception as e:
            print(f"[ImageService] doubao 生图异常: {e}")
            return None

    async def _call_gemini_api(self, prompt: str, use_changhuai: bool = False) -> Optional[str]:
        """调用 Gemini 图片生成 API"""
        if use_changhuai:
            api_key = self.api_key_ch
            base_url = self.base_url_ch
            model = self.model_ch
            tag = "Gemini-CH"
        else:
            api_key = self.api_key
            base_url = self.base_url
            model = self.model
            tag = "Gemini"

        url = f"{base_url}/v1beta/models/{model}:generateContent"
        print(f"[ImageService] {tag} 请求 URL: {url}")
        print(f"[ImageService] {tag} 使用模型: {model}")
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                if "candidates" in result and result["candidates"]:
                    for part in result["candidates"][0]["content"]["parts"]:
                        if "inlineData" in part:
                            return part["inlineData"]["data"]
                
                print(f"[ImageService] {tag} 响应中未找到图片数据")
                return None
                
        except httpx.HTTPStatusError as e:
            print(f"[ImageService] {tag} HTTP 错误: {e.response.status_code}")
            return None
        except Exception as e:
            print(f"[ImageService] {tag} 请求异常: {e}")
            return None

    async def _call_gpt_image_api(self, prompt: str) -> Optional[str]:
        """调用 GPT Image 2 生图 API（OpenAI 兼容，changhuai 渠道）"""
        api_key = self.gpt_image_api_key
        base_url = self.gpt_image_base_url
        model = self.gpt_image_model

        if not api_key:
            print("[ImageService] GPT_IMAGE_API_KEY 未配置")
            return None

        url = f"{base_url}/v1/images/generations"
        print(f"[ImageService] GPT-Image 请求 URL: {url}")
        print(f"[ImageService] GPT-Image 使用模型: {model}")

        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                data_list = result.get("data", [])
                if data_list:
                    item = data_list[0]
                    # 优先使用 b64_json
                    if item.get("b64_json"):
                        return item["b64_json"]
                    # 否则下载 URL 中的图片
                    if item.get("url"):
                        img_resp = await client.get(item["url"], timeout=60.0)
                        img_resp.raise_for_status()
                        return base64.b64encode(img_resp.content).decode("utf-8")

                print(f"[ImageService] GPT-Image 生图无图片: {str(result)[:200]}")
                return None
        except httpx.HTTPStatusError as e:
            print(f"[ImageService] GPT-Image HTTP 错误: {e.response.status_code} {e.response.text[:200]}")
            return None
        except Exception as e:
            print(f"[ImageService] GPT-Image 请求异常: {e}")
            return None

    async def generate_single_image(
        self,
        prompt: str,
        optimize_for_xhs: bool = True,
        provider_override: Optional[str] = None,
    ) -> Optional[str]:
        """生成单张图片（失败时使用备用提示词重试一次）"""
        current_prompt = self.XHS_STYLE_PROMPT.format(content=prompt) if optimize_for_xhs else prompt
        
        effective = self._get_effective_provider(provider_override)
        print(f"[ImageService] 生成图片 (引擎={effective}): {prompt[:50]}...")
        
        # 首次尝试
        image_base64 = await self._call_image_api(current_prompt, provider_override=provider_override)
        if image_base64:
            image_path = self._save_image(image_base64)
            print(f"[ImageService] 图片生成成功: {image_path}")
            return image_path
        
        # 使用备用提示词重试
        print(f"[ImageService] 首次失败，使用备用提示词重试...")
        await asyncio.sleep(1)
        
        fallback_prompt = random.choice(self.FALLBACK_PROMPTS)
        image_base64 = await self._call_image_api(fallback_prompt, provider_override=provider_override)
        if image_base64:
            image_path = self._save_image(image_base64)
            print(f"[ImageService] 备用提示词成功: {image_path}")
            return image_path
        
        print(f"[ImageService] 图片生成失败，跳过")
        return None

    async def generate_images(
        self,
        visual_points: List[str],
        optimize_for_xhs: bool = True,
        provider_override: Optional[str] = None,
    ) -> List[str]:
        """批量生成配图（并行）"""
        if not visual_points:
            return []

        tasks = [
            self.generate_single_image(
                prompt=point,
                optimize_for_xhs=optimize_for_xhs,
                provider_override=provider_override,
            )
            for point in visual_points
        ]
        results = await asyncio.gather(*tasks)

        image_paths = [path for path in results if path is not None]
        print(f"[ImageService] 成功生成 {len(image_paths)}/{len(visual_points)} 张图片")
        return image_paths


# 单例实例
image_service = ImageService()
