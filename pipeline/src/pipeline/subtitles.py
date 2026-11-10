"""단어 타이밍 → 자막 큐 → SRT. 실제 음성 길이 기반 시간 계산(리스크 대응: 자막 싱크 오류)."""

from __future__ import annotations

import re

MAX_CUE_CHARS = 14
MIN_CUE_SEC = 0.6


def words_to_cues(words: list[dict], narration: str, duration: float, max_chars: int = MAX_CUE_CHARS) -> list[dict]:
    if not words:
        return _proportional(narration, duration, max_chars)
    cues, cur = [], []

    def flush():
        if cur:
            cues.append({"text": " ".join(w["text"] for w in cur), "start": cur[0]["start"], "end": cur[-1]["end"]})
            cur.clear()

    for w in words:
        joined = " ".join(x["text"] for x in [*cur, w])
        if cur and len(joined) > max_chars:
            flush()
        cur.append(w)
        if re.search(r"[.?!,]$", w["text"]) and len(" ".join(x["text"] for x in cur)) >= 6:
            flush()
    flush()
    # 큐 사이 빈틈을 다음 큐 시작까지 늘려 깜빡임을 없애고, 너무 짧은 큐는 최소 길이 보장
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else max(duration, c["end"])
        end = nxt if nxt - c["end"] < 0.5 else c["end"]  # 짧은 빈틈은 다음 큐까지 이어 붙임
        end = max(end, min(nxt, c["start"] + MIN_CUE_SEC))  # 다음 큐를 넘지 않는 선에서 최소 길이
        c["start"], c["end"] = round(c["start"], 3), round(end, 3)
    return cues


def _proportional(text: str, duration: float, max_chars: int) -> list[dict]:
    toks = text.split()
    chunks, cur = [], ""
    for t in toks:
        if cur and len(cur) + 1 + len(t) > max_chars:
            chunks.append(cur)
            cur = t
        else:
            cur = f"{cur} {t}".strip()
    if cur:
        chunks.append(cur)
    total = sum(len(c) for c in chunks) or 1
    t, out = 0.0, []
    for c in chunks:
        d = duration * len(c) / total
        out.append({"text": c, "start": round(t, 3), "end": round(t + d, 3)})
        t += d
    return out


def _ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[dict], offset: float = 0.0, start_index: int = 1) -> str:
    blocks = []
    for i, c in enumerate(cues, start_index):
        blocks.append(f"{i}\n{_ts(c['start'] + offset)} --> {_ts(c['end'] + offset)}\n{c['text']}\n")
    return "\n".join(blocks)
