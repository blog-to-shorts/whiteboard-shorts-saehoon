"""이미지 생성 어댑터. IMAGE_PROVIDER=openai | placeholder.

placeholder 는 API 키 없이 파이프라인 전체를 돌려 보는 개발·스모크 테스트 전용이다(품질 평가 대상 아님).
"""

from __future__ import annotations

import base64
import textwrap
from pathlib import Path

from ..config import env

# 1024x1536 1장 기준 USD. 확인된 단가만 넣는다(없으면 비용 '미확인'으로 기록하고 장수만 남김).
IMAGE_PRICES = {"gpt-image-1": {"low": 0.016, "medium": 0.063, "high": 0.25}}
SIZE = (1024, 1536)  # 2:3 세로. Remotion 에서 9:16 화면 안에 배치


class OpenAIImage:
    name = "openai"

    def __init__(self):
        key = env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY 가 없어 화이트보드 이미지를 만들 수 없습니다. 사용자 환경변수 또는 .env 에 넣으세요. "
                "(키 없이 흐름만 확인하려면 IMAGE_PROVIDER=placeholder)")
        from openai import OpenAI

        self.client = OpenAI(api_key=key, max_retries=2, timeout=300)
        self.model = env("OPENAI_IMAGE_MODEL", "gpt-image-2")
        self.quality = env("OPENAI_IMAGE_QUALITY", "medium")

    @property
    def label(self) -> str:
        return f"openai:{self.model}:{self.quality}"

    def cost_per_image(self) -> float | None:
        return IMAGE_PRICES.get(self.model, {}).get(self.quality)

    def generate(self, prompt: str, out: Path) -> None:
        r = self.client.images.generate(model=self.model, prompt=prompt, size=f"{SIZE[0]}x{SIZE[1]}",
                                        quality=self.quality, n=1)
        out.write_bytes(base64.b64decode(r.data[0].b64_json))


class PlaceholderImage:
    """키 없이 동작 확인용: 장면 번호·캡션을 손글씨풍 선으로 그린 단순 그림."""

    name = "placeholder"
    label = "placeholder"

    def cost_per_image(self) -> float:
        return 0.0

    def generate(self, prompt: str, out: Path, caption: str = "", index: int = 1) -> None:
        from PIL import Image, ImageDraw, ImageFont

        im = Image.new("RGB", SIZE, "white")
        d = ImageDraw.Draw(im)
        w, h = SIZE
        font_path = Path("C:/Windows/Fonts/malgunbd.ttf")
        big = ImageFont.truetype(str(font_path), 92) if font_path.exists() else ImageFont.load_default()
        small = ImageFont.truetype(str(font_path.with_name("malgun.ttf")), 38) if font_path.exists() else big
        # 단순 도형: 장면마다 다른 아이콘(원·사각형·화살표·별모양 선)
        cx, cy, r = w // 2, int(h * 0.38), 230
        kind = index % 4
        if kind == 1:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline="black", width=14)
            d.ellipse([cx - 90, cy - 60, cx - 40, cy - 10], fill="black")
            d.ellipse([cx + 40, cy - 60, cx + 90, cy - 10], fill="black")
            d.arc([cx - 120, cy - 20, cx + 120, cy + 140], 20, 160, fill="black", width=14)
        elif kind == 2:
            d.rounded_rectangle([cx - 260, cy - 200, cx + 260, cy + 200], 40, outline="black", width=14)
            for k in range(3):
                d.line([cx - 180, cy - 100 + k * 100, cx + 180, cy - 100 + k * 100], fill="black", width=12)
        elif kind == 3:
            d.line([cx - 300, cy, cx + 220, cy], fill="black", width=16)
            d.polygon([(cx + 300, cy), (cx + 200, cy - 80), (cx + 200, cy + 80)], fill="black")
            d.ellipse([cx - 380, cy - 80, cx - 220, cy + 80], outline="black", width=14)
        else:
            d.polygon([(cx, cy - r), (cx + r, cy + r // 2), (cx - r, cy + r // 2)], outline="black", width=14)
            d.line([cx, cy - r // 3, cx, cy + r // 4], fill="black", width=16)
        if caption:
            d.text((cx, int(h * 0.68)), caption, font=big, fill="black", anchor="mm")
        lines = textwrap.wrap(f"PLACEHOLDER {index}: {prompt}", 44)[:4]
        for i, ln in enumerate(lines):
            d.text((cx, int(h * 0.8) + i * 50), ln, font=small, fill="black", anchor="mm")
        im.save(out)


def get_image_provider(name: str | None = None):
    name = (name or env("IMAGE_PROVIDER", "openai")).lower()
    if name == "openai":
        return OpenAIImage()
    if name == "placeholder":
        return PlaceholderImage()
    raise ValueError(f"알 수 없는 IMAGE_PROVIDER: {name} (openai | placeholder)")


def postprocess(path: Path, grayscale: bool, white_threshold: int) -> None:
    """드로잉 엔진 입력 조건(흰 배경 위 잉크)에 맞춘다: 거의 흰색은 순백으로, 흑백 프리셋은 회색조로."""
    from PIL import Image
    import numpy as np

    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    if grayscale:
        g = (a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114).astype(np.int16)
        a = np.stack([g, g, g], axis=-1)
    if white_threshold:
        light = a.min(axis=-1) >= white_threshold
        a[light] = 255
    Image.fromarray(a.clip(0, 255).astype("uint8")).save(path)
