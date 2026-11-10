"""설정: 환경변수(.env 포함)에서 읽는다. 키 값은 로그·결과물에 절대 쓰지 않는다."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # whiteboard-shorts/
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
REMOTION_DIR = PROJECT_ROOT / "remotion"


def _load_dotenv(path: Path) -> None:
    """의존성 없이 .env 를 읽는다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and k not in os.environ:
            os.environ[k] = v


_load_dotenv(PROJECT_ROOT / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, "") or default


@dataclass
class Settings:
    llm_provider: str = field(default_factory=lambda: env("LLM_PROVIDER", "openai"))
    image_provider: str = field(default_factory=lambda: env("IMAGE_PROVIDER", "openai"))
    tts_provider: str = field(default_factory=lambda: env("TTS_PROVIDER", "edge"))
    animator: str = field(default_factory=lambda: env("ANIMATOR", "whiteboard"))  # whiteboard | simple
    style_preset: str = field(default_factory=lambda: env("STYLE_PRESET", "marker_mono"))
    prompt_version: str = field(default_factory=lambda: env("PROMPT_VERSION", "v2"))
    scene_count: int = 5
    target_duration: int = 45  # 초. 30~60 범위 안에서 목표
    fps: int = 30
    width: int = 1080
    height: int = 1920
    jobs_dir: Path = field(default_factory=lambda: Path(env("JOBS_DIR", str(PROJECT_ROOT / "jobs"))).resolve())

    def public(self) -> dict:
        """결과물(scenes.json meta)에 남겨도 되는 설정만."""
        return {
            "llm_provider": self.llm_provider,
            "image_provider": self.image_provider,
            "tts_provider": self.tts_provider,
            "animator": self.animator,
            "style_preset": self.style_preset,
            "prompt_version": self.prompt_version,
            "scene_count": self.scene_count,
            "target_duration": self.target_duration,
        }
