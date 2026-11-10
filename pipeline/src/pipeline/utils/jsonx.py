"""LLM 응답에서 JSON 꺼내기."""

from __future__ import annotations

import json
import re


def extract_json(text: str):
    """첫 번째 완전한 JSON 객체만 읽는다(뒤에 붙은 설명·두 번째 객체는 무시)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError("응답에 JSON 이 없습니다: " + text[:200])
    obj, _ = json.JSONDecoder().raw_decode(text[min(starts):])
    return obj
