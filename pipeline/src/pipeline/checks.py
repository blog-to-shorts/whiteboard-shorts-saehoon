"""대본 자동 검사 규칙. STEP 03 (생성 직후 자체 수정)과 5단계 평가가 같은 기준을 쓴다.

길이 기준은 Edge 한국어 음성(SunHi, +8%) 실측 약 6.1자/초에서 거꾸로 계산했다.
30~60초 영상 = 장면 여백(0.4초 × 장면 수)을 빼고 음성 약 28~55초 → 내레이션 합계 170~330자.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CHARS_PER_SEC = 6.1
SCENE_PAD_SEC = 0.4
BANNED = re.compile(r"[\U0001F300-\U0001FAFF☀-➿※★☆▶►•|]")


@dataclass(frozen=True)
class Limits:
    hook_max: int = 18
    caption_max: int = 16
    narr_min: int = 25
    narr_max: int = 75
    total_min: int = 170
    total_max: int = 330
    scenes_min: int = 4
    scenes_max: int = 8
    min_sec: float = 30.0
    max_sec: float = 60.0


LIMITS = Limits()


def clen(s) -> int:
    return len(str(s or ""))


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def source_match(part: str, source_norm: str) -> float:
    """근거 문장이 원문에 얼마나 그대로 있는지 0~1. 1=글자 그대로, 공백 무시.
    완전 일치가 아니면 원문에서 가장 길게 이어지는 공통 구간 / 근거 길이."""
    p = _norm(part)
    if not p:
        return 0.0
    if p in source_norm:
        return 1.0
    from difflib import SequenceMatcher

    m = SequenceMatcher(None, p, source_norm, autojunk=False).find_longest_match(0, len(p), 0, len(source_norm))
    return round(m.size / len(p), 3)


SOURCE_OK = 0.6  # 이 이상이면 '거의 그대로'(경고만), 미만이면 원문에 없는 근거(오류)


def estimate_seconds(narrations: list[str]) -> float:
    total = sum(clen(n) for n in narrations)
    return round(total / CHARS_PER_SEC + SCENE_PAD_SEC * len(narrations), 1)


def check_script(hook: str, scenes: list[dict], source_text: str, limits: Limits = LIMITS) -> list[dict]:
    """문제 목록. 각 항목: {code, scene(0=전체), msg}."""
    out: list[dict] = []

    def add(code: str, scene: int, msg: str):
        out.append({"code": code, "scene": scene, "msg": msg})

    if not hook:
        add("hook_missing", 0, "hook 이 비어 있음")
    elif clen(hook) > limits.hook_max:
        add("hook_long", 0, f"hook {clen(hook)}자 > {limits.hook_max}자")
    if not (limits.scenes_min <= len(scenes) <= limits.scenes_max):
        add("scene_count", 0, f"장면 {len(scenes)}개 ({limits.scenes_min}~{limits.scenes_max}개여야 함)")

    src = _norm(source_text)
    total = 0
    for i, s in enumerate(scenes, 1):
        n = clen(s.get("narration"))
        total += n
        if not s.get("narration"):
            add("narr_missing", i, f"장면 {i}: narration 없음")
        elif not (limits.narr_min <= n <= limits.narr_max):
            add("narr_len", i, f"장면 {i}: narration {n}자 ({limits.narr_min}~{limits.narr_max}자여야 함)")
        if not s.get("caption"):
            add("caption_missing", i, f"장면 {i}: caption 없음")
        elif clen(s["caption"]) > limits.caption_max:
            add("caption_long", i, f"장면 {i}: caption {clen(s['caption'])}자 > {limits.caption_max}자")
        if not s.get("image_prompt"):
            add("image_prompt_missing", i, f"장면 {i}: image_prompt 없음")
        for k in ("caption", "narration"):
            if BANNED.search(str(s.get(k) or "")):
                add("banned_char", i, f"장면 {i}: {k} 에 이모지·특수기호")
        parts = s.get("source") or []
        parts = parts if isinstance(parts, list) else [parts]
        parts = [p for p in parts if p]
        if not parts:
            add("source_missing", i, f"장면 {i}: source 없음")
        elif src:
            worst = min(source_match(p, src) for p in parts)
            if worst < SOURCE_OK:
                add("source_not_found", i, f"장면 {i}: source 가 원문에 없음(일치 {worst:.0%}) — 원문 문장을 그대로 복사할 것")
    if not (limits.total_min <= total <= limits.total_max):
        add("total_len", 0, f"narration 합계 {total}자 ({limits.total_min}~{limits.total_max}자여야 함)")
    return out
