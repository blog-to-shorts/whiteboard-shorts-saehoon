"""TTS 어댑터. TTS_PROVIDER=edge | elevenlabs.

synthesize(text, out) → 단어별 타이밍 리스트 [{text, start, end}] (초). 자막(SRT) 싱크에 그대로 쓴다.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import httpx

from ..config import env


class EdgeTTS:
    """Microsoft Edge 신경망 음성 (무료, 키 불필요, 인터넷 필요)."""

    name = "edge"

    def __init__(self, rate: str | None = None):
        self.voice = env("EDGE_VOICE", "ko-KR-SunHiNeural")
        self.rate = rate or env("EDGE_RATE", "+8%")

    @property
    def label(self) -> str:
        return f"edge:{self.voice}:{self.rate}"

    def synthesize(self, text: str, out: Path) -> list[dict]:
        import edge_tts

        async def go():
            words: list[dict] = []
            com = edge_tts.Communicate(text, self.voice, rate=self.rate, boundary="WordBoundary")
            with out.open("wb") as f:
                async for chunk in com.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        s = chunk["offset"] / 1e7
                        words.append({"text": chunk["text"], "start": round(s, 3),
                                      "end": round(s + chunk["duration"] / 1e7, 3)})
            return words

        return asyncio.run(go())


class ElevenLabsTTS:
    """ElevenLabs (유료). with-timestamps 응답의 글자 정렬로 단어 타이밍을 만든다."""

    name = "elevenlabs"

    def __init__(self):
        self.key = env("ELEVENLABS_API_KEY")
        self.voice = env("ELEVENLABS_VOICE_ID")
        self.model = env("ELEVENLABS_MODEL", "eleven_multilingual_v2")
        if not self.key or not self.voice:
            raise RuntimeError("ELEVENLABS_API_KEY 와 ELEVENLABS_VOICE_ID 가 필요합니다 (또는 TTS_PROVIDER=edge).")

    @property
    def label(self) -> str:
        return f"elevenlabs:{self.model}"

    def synthesize(self, text: str, out: Path) -> list[dict]:
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice}/with-timestamps",
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": self.key},
            json={"text": text, "model_id": self.model},
            timeout=120,
        )
        if r.status_code >= 400:  # ElevenLabs 는 이유를 JSON detail 로 준다(결제·권한·목소리 문제 구분용)
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise RuntimeError(f"ElevenLabs {r.status_code}: {str(detail)[:300]}")
        data = r.json()
        out.write_bytes(base64.b64decode(data["audio_base64"]))
        al = data.get("alignment") or {}
        chars = al.get("characters", [])
        starts = al.get("character_start_times_seconds", [])
        ends = al.get("character_end_times_seconds", [])
        words, cur, s0, e0 = [], "", None, None
        for ch, s, e in zip(chars, starts, ends):
            if ch.isspace():
                if cur:
                    words.append({"text": cur, "start": s0, "end": e0})
                cur, s0 = "", None
                continue
            cur += ch
            s0 = s if s0 is None else s0
            e0 = e
        if cur:
            words.append({"text": cur, "start": s0, "end": e0})
        return words


def get_tts(name: str | None = None, **kw):
    name = (name or env("TTS_PROVIDER", "edge")).lower()
    if name == "edge":
        return EdgeTTS(**kw)
    if name == "elevenlabs":
        return ElevenLabsTTS()
    raise ValueError(f"알 수 없는 TTS_PROVIDER: {name} (edge | elevenlabs)")
