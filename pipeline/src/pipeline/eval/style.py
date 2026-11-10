"""그림체 일관성 측정 (장면 이미지 간 비교).

이미지마다 화이트보드 적합도 지표를 재고, 장면 간 변동계수(CV = 표준편차/평균)로 일관성을 본다.
- white_bg: 흰 배경 비율 (드로잉 엔진 입력 조건: 흰 바탕 위 잉크)
- ink: 잉크(선·면) 비율
- gray_tones: 잉크 중 회색(0.25~0.8 밝기) 비율 — 음영·그라데이션이 많을수록 높음
- colorfulness: Hasler–Süsstrunk 채도 지표 (흑백 프리셋이면 ~0)
- stroke_px: 선 굵기 중앙값(px, 거리변환×2)
- detail: 가장자리 밀도(Canny) — 묘사가 복잡할수록 높음
- text_area: 글자 영역 비율(CRAFT 텍스트 검출, whiteboard-animator 에 포함). 달력 칸·동전 무늬 같은 반복 도형을
  글자로 잡는 오탐이 있어 장면 단위 판정에는 쓰지 않고, 작업(장면 평균) 단위 참고 지표로만 쓴다.
"""

from __future__ import annotations

import statistics
from pathlib import Path

import numpy as np

# 장면 간 일관성 기준(변동계수 상한)과 개별 이미지 기준
THRESHOLDS = {
    "white_bg_min": 0.55,
    "gray_tones_max": 0.25,
    "colorfulness_max_mono": 8.0,
    "cv_stroke_px_max": 0.35,
    "cv_ink_max": 0.6,
    "cv_detail_max": 0.6,
    "text_area_mean_max": 0.008,  # 개선 전(글자 있음) 0.010~0.072, 개선 후 0.003~0.005 실측으로 정함
}

_craft = None


def text_area(rgb) -> float | None:
    """CRAFT 글자 영역 비율. 드로잉 엔진이 없으면 None."""
    global _craft
    try:
        if _craft is None:
            from whiteboard_animator.craft_detector import CRAFTDetector

            _craft = CRAFTDetector()
        return round(float(_craft.detect(rgb).mean()), 4)
    except Exception:  # noqa: BLE001 — 선택 지표
        return None


def image_metrics(path: Path) -> dict:
    import cv2

    bgr = cv2.imread(str(path))
    if bgr is None:
        raise ValueError(f"이미지를 읽을 수 없음: {path}")
    h, w = bgr.shape[:2]
    scale = 1024 / max(h, w)
    if scale < 1:
        bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    ink = gray < 0.94
    ink_ratio = float(ink.mean())
    gray_tones = float(((gray >= 0.25) & (gray <= 0.8)).sum() / max(1, ink.sum()))
    b, g, r = [c.astype(np.float32) for c in cv2.split(bgr)]
    rg, yb = r - g, 0.5 * (r + g) - b
    colorful = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
    dist = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)
    skel_vals = dist[(dist > 0) & (cv2.dilate(dist, np.ones((3, 3))) == dist)]
    stroke = float(np.median(skel_vals) * 2) if skel_vals.size else 0.0
    edges = cv2.Canny((gray * 255).astype(np.uint8), 80, 160)
    out = {
        "white_bg": round(1 - ink_ratio, 3), "ink": round(ink_ratio, 3), "gray_tones": round(gray_tones, 3),
        "colorfulness": round(colorful, 2), "stroke_px": round(stroke, 2), "detail": round(float((edges > 0).mean()), 4),
    }
    ta = text_area(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    if ta is not None:
        out["text_area"] = ta
    return out


def _cv(vals: list[float]) -> float:
    m = statistics.mean(vals)
    return round(statistics.pstdev(vals) / m, 3) if m else 0.0


def style_report(images: list[Path], mono: bool = True) -> dict:
    per = {p.name: image_metrics(p) for p in images}
    rows = list(per.values())
    keys = ["ink", "stroke_px", "detail", "gray_tones", "colorfulness"]
    cv = {k: _cv([r[k] for r in rows]) for k in keys} if len(rows) > 1 else {k: 0.0 for k in keys}
    t = THRESHOLDS
    checks = {
        "흰 배경(모든 장면)": all(r["white_bg"] >= t["white_bg_min"] for r in rows),
        "음영·회색 적음(모든 장면)": all(r["gray_tones"] <= t["gray_tones_max"] for r in rows),
        "선 굵기 일관(CV)": cv["stroke_px"] <= t["cv_stroke_px_max"],
        "잉크 양 일관(CV)": cv["ink"] <= t["cv_ink_max"],
        "복잡도 일관(CV)": cv["detail"] <= t["cv_detail_max"],
    }
    if mono:
        checks["흑백 유지(모든 장면)"] = all(r["colorfulness"] <= t["colorfulness_max_mono"] for r in rows)
    text_mean = None
    if rows and all("text_area" in r for r in rows):
        text_mean = round(statistics.mean(r["text_area"] for r in rows), 4)
        checks["그림 속 글자 거의 없음(장면 평균)"] = text_mean <= t["text_area_mean_max"]
    score = round(sum(checks.values()) / len(checks), 2)
    return {"images": per, "cv": cv, "checks": checks, "consistency_score": score, "text_area_mean": text_mean}
