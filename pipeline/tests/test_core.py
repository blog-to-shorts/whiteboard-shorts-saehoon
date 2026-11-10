"""API 키 없이 도는 단위 테스트: 대본 검사 규칙, 자막 생성, scenes.json 스키마, 이미지 지표."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from pipeline.checks import check_script, estimate_seconds, source_match
from pipeline.eval.style import image_metrics, style_report
from pipeline.schema import ScenesDoc
from pipeline.subtitles import to_srt, words_to_cues

SRC = "오늘은 목동 안양천을 달렸어요. 왕복 10km 평지라서 초보자도 뛰기 좋습니다. 화장실은 2곳뿐이에요."


def _scene(n="안양천은 왕복 십 킬로미터 평지라 초보자도 부담 없이 뛰기 좋아요.", src="왕복 10km 평지라서 초보자도 뛰기 좋습니다."):
    return {"caption": "왕복 10km 평지", "narration": n, "image_prompt": "a runner on a flat riverside path", "source": [src]}


def test_check_script_passes_good_script():
    scenes = [_scene() for _ in range(5)]
    scenes[0]["narration"] = "퇴근 후 어디서 뛸지 고민이라면 목동 안양천 코스를 한번 보세요. 평지라서 처음 뛰는 분께 잘 맞아요."
    problems = check_script("초보 러너 코스", scenes, SRC)
    assert [p for p in problems if p["code"] != "total_len"] == []


def test_check_script_flags_long_and_ungrounded():
    bad = _scene(n="가" * 120, src="원문에 전혀 없는 문장입니다 정말로요")
    codes = {p["code"] for p in check_script("이 훅은 너무 길어서 기준을 넘는 문구입니다", [bad], SRC)}
    assert {"hook_long", "scene_count", "narr_len", "source_not_found", "total_len"} <= codes


def test_check_script_flags_text_in_image_prompt():
    bad = [_scene() for _ in range(5)]
    bad[1]["image_prompt"] = "a house key icon, document labeled '등기부등본'"
    bad[2]["image_prompt"] = "two ID cards with the word owner"
    codes = [(p["code"], p["scene"]) for p in check_script("초보 러너 코스", bad, SRC)]
    assert ("image_prompt_text", 2) in codes and ("image_prompt_text", 3) in codes
    assert ("image_prompt_text", 1) not in codes  # 'a runner on a flat riverside path' 는 통과


def test_source_match_ignores_whitespace_and_scores_partial():
    norm = SRC.replace(" ", "")
    assert source_match("왕복 10km  평지라서", norm) == 1.0
    assert 0.6 <= source_match("왕복 10km 평지라서 초보자가 뛰기 좋습니다.", norm) < 1.0


def test_extract_json_ignores_trailing_text():
    from pipeline.utils.jsonx import extract_json

    assert extract_json('설명입니다 {"a": 1, "b": "}"} 그리고 {"c": 2}') == {"a": 1, "b": "}"}
    assert extract_json('```json\n{"x": [1, 2]}\n```') == {"x": [1, 2]}


def test_estimate_seconds_in_target_range():
    assert 30 <= estimate_seconds(["가" * 50] * 5) <= 60


def test_words_to_cues_groups_and_has_no_gaps():
    words = [{"text": t, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, t in enumerate("탁 트인 바다와 푸른 산을 보며 쉬고 싶을 때".split())]
    cues = words_to_cues(words, "", 4.0)
    assert all(len(c["text"]) <= 14 for c in cues)
    assert all(cues[i]["end"] >= cues[i + 1]["start"] - 0.5 for i in range(len(cues) - 1))
    srt = to_srt(cues, offset=10)
    assert srt.startswith("1\n00:00:10,000 --> ")


def test_words_to_cues_falls_back_to_proportional():
    cues = words_to_cues([], "하나 둘 셋 넷 다섯 여섯 일곱 여덟 아홉 열", 5.0)
    assert cues[0]["start"] == 0 and abs(cues[-1]["end"] - 5.0) < 0.01


def test_scenes_doc_scene_count_is_data_driven():
    doc = ScenesDoc(title="t", scenes=[{"id": i, "narration": "n"} for i in range(1, 8)])
    assert len(doc.scenes) == 7 and doc.aspect_ratio == "9:16"


def _draw(path: Path, width: int, color=(0, 0, 0)):
    im = Image.new("RGB", (400, 600), "white")
    d = ImageDraw.Draw(im)
    d.ellipse([100, 150, 300, 350], outline=color, width=width)
    im.save(path)


def test_style_metrics_detects_inconsistent_strokes(tmp_path):
    a, b, c = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    _draw(a, 8)
    _draw(b, 8)
    _draw(c, 40, color=(220, 40, 40))
    m = image_metrics(a)
    assert m["white_bg"] > 0.9 and 5 <= m["stroke_px"] <= 12 and m["colorfulness"] < 1
    consistent = style_report([a, b])
    mixed = style_report([a, b, c])
    assert consistent["consistency_score"] > mixed["consistency_score"]
    assert mixed["checks"]["흑백 유지(모든 장면)"] is False
