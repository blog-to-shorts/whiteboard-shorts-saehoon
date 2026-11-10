"""대본 자동 지표 + 완성 작업(영상) 지표."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..checks import LIMITS, SOURCE_OK, _norm, check_script, clen, estimate_seconds, source_match


def script_metrics(hook: str, scenes: list[dict], source_text: str) -> dict:
    problems = check_script(hook, scenes, source_text)
    src = _norm(source_text)
    matches = []
    for s in scenes:
        parts = s.get("source") or []
        parts = [p for p in (parts if isinstance(parts, list) else [parts]) if p]
        matches.append(min((source_match(p, src) for p in parts), default=0.0))
    est = estimate_seconds([s.get("narration", "") for s in scenes])
    codes = {p["code"] for p in problems}
    return {
        "scene_count": len(scenes),
        "narration_chars": sum(clen(s.get("narration")) for s in scenes),
        "est_seconds": est,
        "length_ok": LIMITS.min_sec <= est <= LIMITS.max_sec,
        "structure_ok": not (codes & {"scene_count", "hook_missing", "narr_missing", "caption_missing",
                                      "image_prompt_missing"}),
        "format_violations": len([p for p in problems if p["code"] not in ("source_not_found", "source_missing")]),
        "grounded_rate": round(sum(m >= SOURCE_OK for m in matches) / max(1, len(matches)), 3),
        "exact_source_rate": round(sum(m >= 1.0 for m in matches) / max(1, len(matches)), 3),
        "problems": [p["msg"] for p in problems],
    }


def job_metrics(job_dir: Path) -> dict:
    """완성 작업: 길이·싱크·시간·비용·수정 이력."""
    from ..utils.ffmpeg import probe_duration

    doc = json.loads((job_dir / "scenes.json").read_text(encoding="utf-8"))
    m = json.loads((job_dir / "metrics.json").read_text(encoding="utf-8"))
    final = job_dir / "final.mp4"
    video_sec = probe_duration(final) if final.is_file() else None
    # 자막 싱크: 큐 시작이 실제 발화(단어 타이밍) 시작과 얼마나 다른지(초)
    drifts = []
    for s in doc["scenes"]:
        starts = [w["start"] for w in s.get("words", [])]
        for c in s.get("cues", []):
            if starts:
                drifts.append(min(abs(c["start"] - w) for w in starts))
    srt = (job_dir / "subtitles.srt").read_text(encoding="utf-8") if (job_dir / "subtitles.srt").is_file() else ""
    srt_end = 0.0
    for h, mi, se, ms in re.findall(r"--> (\d+):(\d+):(\d+),(\d+)", srt):
        srt_end = max(srt_end, int(h) * 3600 + int(mi) * 60 + int(se) + int(ms) / 1000)
    costs = [v.get("cost_usd") for v in m.get("cost", {}).values()]
    return {
        "video_seconds": round(video_sec, 2) if video_sec else None,
        "duration_ok": bool(video_sec and LIMITS.min_sec <= video_sec <= LIMITS.max_sec),
        "voice_seconds": doc.get("meta", {}).get("voice_seconds"),
        "subtitle_max_drift_sec": round(max(drifts), 3) if drifts else None,
        "subtitle_within_video": bool(video_sec and srt_end <= video_sec + 0.05),
        "generation_seconds": m.get("total_seconds"),
        "step_seconds": {k: v["seconds"] for k, v in m.get("steps", {}).items()},
        "cost_usd": None if any(c is None for c in costs) else round(sum(costs), 4),
        "cost_detail": m.get("cost", {}),
        "animator": doc.get("meta", {}).get("animator"),
        "edited": (job_dir / "edits.json").is_file(),
    }
