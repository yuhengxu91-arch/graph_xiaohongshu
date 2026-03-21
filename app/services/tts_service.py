"""
TTS 语音合成服务
使用火山引擎 TTS HTTP 接口（一次性合成）

如果未配置 TTS 凭证，则降级为生成静音音频文件（方便流程调试）
"""
import os
import uuid
import json
import base64
import asyncio
from pathlib import Path
from typing import List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

# 音频存储目录
AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


class TTSService:
    """火山引擎 TTS 服务"""

    def __init__(self):
        self.app_id = os.getenv("TTS_APP_ID", "")
        self.access_token = os.getenv("TTS_ACCESS_TOKEN", "")
        self.voice_type = os.getenv("TTS_VOICE_TYPE", "zh_female_cancan_mars")
        self.api_url = os.getenv(
            "TTS_API_URL",
            "https://openspeech.bytedance.com/api/v1/tts"
        )
        self._semaphore = asyncio.Semaphore(3)  # 并发限流

        if not self.app_id or not self.access_token:
            print("[TTS] ⚠️  未配置火山引擎 TTS 凭证，将使用静音音频降级模式")
        else:
            print(f"[TTS] 已配置火山引擎 TTS（音色: {self.voice_type}）")

    @property
    def is_configured(self) -> bool:
        """是否已配置真实 TTS 服务"""
        return bool(self.app_id and self.access_token)

    async def synthesize(
        self,
        text: str,
        voice_type: Optional[str] = None,
        speed_ratio: float = 1.0,
    ) -> dict:
        """
        单段文本合成

        Returns:
            {
                "audio_path": "static/audio/xxx.mp3",
                "audio_url": "/static/audio/xxx.mp3",
                "duration": 5.0  (估算)
            }
        """
        if not self.is_configured:
            return await self._generate_silent_audio(text)

        async with self._semaphore:
            return await self._call_volcano_tts(text, voice_type, speed_ratio)

    async def batch_synthesize(
        self,
        segments: List[str],
        voice_type: Optional[str] = None,
        speed_ratio: float = 1.0,
    ) -> List[dict]:
        """
        批量合成（并发限流）

        Args:
            segments: 文本列表
        Returns:
            [{ audio_path, audio_url, duration }, ...]
        """
        tasks = [
            self.synthesize(text, voice_type, speed_ratio)
            for text in segments
        ]
        return await asyncio.gather(*tasks)

    async def _call_volcano_tts(
        self,
        text: str,
        voice_type: Optional[str] = None,
        speed_ratio: float = 1.0,
    ) -> dict:
        """调用火山引擎 TTS HTTP 接口"""
        filename = f"{uuid.uuid4().hex}.mp3"
        audio_path = AUDIO_DIR / filename

        payload = {
            "app": {
                "appid": self.app_id,
                "token": "access_token",
                "cluster": "volcano_tts",
            },
            "user": {"uid": "video-generator"},
            "audio": {
                "voice_type": voice_type or self.voice_type,
                "encoding": "mp3",
                "speed_ratio": speed_ratio,
            },
            "request": {
                "reqid": uuid.uuid4().hex,
                "text": text,
                "operation": "query",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.api_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer;{self.access_token}",
                    },
                )
                resp.raise_for_status()
                result = resp.json()

                if result.get("code") != 3000:
                    raise Exception(
                        f"TTS API error: code={result.get('code')}, "
                        f"message={result.get('message')}"
                    )

                # 解码 base64 音频数据
                audio_data = base64.b64decode(result["data"])
                audio_path.write_bytes(audio_data)

                # 估算时长: 中文约 4 字/秒
                estimated_duration = max(2.0, len(text) / 4.0 / speed_ratio)

                print(f"[TTS] 合成成功: {filename} ({len(text)} 字, ~{estimated_duration:.1f}s)")

                return {
                    "audio_path": str(audio_path),
                    "audio_url": f"/static/audio/{filename}",
                    "duration": estimated_duration,
                }

        except Exception as e:
            print(f"[TTS] 合成失败，降级为静音音频: {e}")
            return await self._generate_silent_audio(text)

    async def _generate_silent_audio(self, text: str) -> dict:
        """
        生成静音音频文件（降级模式）
        使用最小有效 MP3 文件，然后根据文本长度估算时长
        """
        filename = f"{uuid.uuid4().hex}.mp3"
        audio_path = AUDIO_DIR / filename

        # 最小有效 MP3 帧（约 0.026 秒静音）
        # 我们写入多个帧来凑足时长
        estimated_duration = max(2.0, len(text) / 4.0)

        # 写入一个空的小文件作为占位
        # 真正的静音可以用 ffmpeg 生成，这里简化处理
        silent_frame = bytes([
            0xFF, 0xFB, 0x90, 0x00,  # MPEG1 Layer3 header
        ] + [0x00] * 413)  # 补齐一帧

        # 写入足够帧数覆盖估算时长
        frames_needed = int(estimated_duration / 0.026) + 1
        with open(audio_path, "wb") as f:
            for _ in range(frames_needed):
                f.write(silent_frame)

        print(f"[TTS] 静音降级: {filename} (~{estimated_duration:.1f}s, {len(text)} 字)")

        return {
            "audio_path": str(audio_path),
            "audio_url": f"/static/audio/{filename}",
            "duration": estimated_duration,
        }


# 单例
tts_service = TTSService()
