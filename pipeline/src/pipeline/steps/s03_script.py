"""STEP 03. 대본 및 장면 생성 → scenes.json.

prompt_version 으로 개선 전(v1)·후(v2) 프롬프트를 바꿔 끼운다(5단계 비교용).
v2 는 생성 직후 자동 검사(checks.py)를 돌려 지적된 항목만 한 번 고쳐 쓰게 한다.
"""

from __future__ import annotations

import json
import re

from ..checks import LIMITS, check_script, estimate_seconds
from ..config import PROMPTS_DIR
from ..schema import Analysis, Scene, ScenesDoc
from .s04_image import load_style

MAX_TEXT = 20000
_STRIP = re.compile(r"[\U0001F300-\U0001FAFF☀-➿※★☆▶►•|]")


def _clean(v) -> str:
    return re.sub(r"\s+", " ", _STRIP.sub("", str(v or ""))).strip()


def build_prompt(version: str, title: str, text: str, analysis: Analysis | None, scene_count: int,
                 target_duration: int) -> str:
    tpl = (PROMPTS_DIR / f"script_{version}.md").read_text(encoding="utf-8")
    a = analysis or Analysis(core_message="")
    values = {
        "title": title, "text": text[:MAX_TEXT], "scene_count": scene_count, "target_duration": target_duration,
        "core_message": a.core_message, "key_points": json.dumps(a.key_points, ensure_ascii=False),
        "facts": json.dumps(a.facts, ensure_ascii=False), "visual_motif": a.visual_motif or "(없음)",
        "hook_max": LIMITS.hook_max, "caption_max": LIMITS.caption_max, "narr_min": LIMITS.narr_min,
        "narr_max": LIMITS.narr_max, "total_min": LIMITS.total_min, "total_max": LIMITS.total_max,
    }
    for k, v in values.items():
        tpl = tpl.replace("{" + k + "}", str(v))
    return tpl


def _normalize(data: dict) -> tuple[str, list[dict]]:
    scenes = []
    for s in data.get("scenes") or []:
        src = s.get("source") or []
        scenes.append({
            "caption": _clean(s.get("caption")),
            "narration": _clean(s.get("narration") or s.get("caption")),
            "image_prompt": str(s.get("image_prompt") or "").strip(),
            "source": src if isinstance(src, list) else [src],
        })
    return _clean(data.get("hook")), scenes


def generate(llm, *, version: str, title: str, text: str, analysis: Analysis | None, scene_count: int,
             target_duration: int, fix: bool = True, log=None) -> dict:
    """대본 생성 + (선택) 자동 검사 기반 1회 수정. 평가 스크립트도 이 함수를 그대로 쓴다."""
    prompt = build_prompt(version, title, text, analysis, scene_count, target_duration)
    messages = [{"role": "user", "content": prompt}]
    hook, scenes = _normalize(llm.chat_json(messages, tag=f"script_{version}"))
    problems = check_script(hook, scenes, text)
    first_problems = list(problems)
    fixed = False
    if fix and problems:
        if log:
            log.info("STEP03: 1차 검사 %d건 → 수정 요청 (%s)", len(problems), " / ".join(p["msg"] for p in problems[:3]))
        messages += [
            {"role": "assistant", "content": json.dumps({"hook": hook, "scenes": scenes}, ensure_ascii=False)},
            {"role": "user", "content": "자동 검사에서 다음 문제가 나왔습니다. 지적된 항목만 고치고 나머지는 그대로 둔 "
                                        "전체 JSON 만 다시 출력하세요.\n- " + "\n- ".join(p["msg"] for p in problems)},
        ]
        try:
            h2, s2 = _normalize(llm.chat_json(messages, tag=f"script_{version}_fix"))
            p2 = check_script(h2, s2, text)
            if len(p2) <= len(problems):
                hook, scenes, problems, fixed = h2, s2, p2, True
        except Exception as e:  # noqa: BLE001
            if log:
                log.warning("STEP03: 수정 요청 실패, 1차 대본 사용: %s", e)
    return {"hook": hook, "scenes": scenes, "problems": problems, "first_problems": first_problems, "fixed": fixed,
            "est_seconds": estimate_seconds([s["narration"] for s in scenes])}


def run(job) -> None:
    st = job.settings
    src, analysis = job.source(), job.analysis()
    out = generate(job.llm, version=st.prompt_version, title=src.title, text=src.text, analysis=analysis,
                   scene_count=st.scene_count, target_duration=st.target_duration,
                   fix=st.prompt_version != "v1", log=job.log)
    style = load_style(st.style_preset)
    doc = ScenesDoc(
        title=src.title, hook=out["hook"], source_url=src.url, fps=st.fps, target_duration=st.target_duration,
        style_preset=st.style_preset, style_prompt=style["prompt"], visual_motif=analysis.visual_motif,
        scenes=[Scene(id=i, **s) for i, s in enumerate(out["scenes"], 1)],
        meta={"prompt_version": st.prompt_version, "llm": job.llm.label, "script_problems": out["problems"],
              "script_first_problems": out["first_problems"], "script_fixed": out["fixed"],
              "est_seconds": out["est_seconds"]},
    )
    job.save_doc(doc)
    job.add_cost("llm", job.llm.summary())
    job.log.info("STEP03: 장면 %d개, 예상 %.1f초, 남은 경고 %d건 (prompt %s)",
                 len(doc.scenes), out["est_seconds"], len(out["problems"]), st.prompt_version)
