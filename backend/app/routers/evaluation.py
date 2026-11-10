"""5단계 평가 결과 요약 API (시연 화면용). eval/runs/ 의 최신 대본·그림체 비교 결과를 돌려준다."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from pipeline.config import PROJECT_ROOT

router = APIRouter(prefix="/api/eval", tags=["evaluation"])
RUNS = PROJECT_ROOT / "eval" / "runs"
FALLBACK = PROJECT_ROOT / "docs" / "eval_summary.json"  # 저장소에 포함되는 요약본(runs/ 는 git 제외)


def _latest_run() -> Path | None:
    if not RUNS.is_dir():
        return None
    runs = sorted((d for d in RUNS.iterdir() if (d / "summary.json").is_file()), key=lambda d: d.name, reverse=True)
    return runs[0] if runs else None


def build_summary() -> dict:
    run = _latest_run()
    if run is None:
        return json.loads(FALLBACK.read_text(encoding="utf-8")) if FALLBACK.is_file() else {}
    script = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    rows = [json.loads(x) for x in (run / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    images = []
    ip = run / "images" / "image_results.json"
    if ip.is_file():
        for r in json.loads(ip.read_text(encoding="utf-8")):
            if "error" in r:
                continue
            images.append({"sample": r["sample"], "style": r["style"], "score": r["consistency_score"],
                           "cv_stroke": r["cv"]["stroke_px"], "text_area": r.get("text_area_mean")})
    return {
        "run": run.name,
        "script": script,
        "samples": sorted({r["sample"] for r in rows}),
        "errors": [f"{r['sample']}/{r['version']}" for r in rows if "error" in r],
        "images": images,
    }


@router.get("/summary")
def summary():
    return build_summary()
