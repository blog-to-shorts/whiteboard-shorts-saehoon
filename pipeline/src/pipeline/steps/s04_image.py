"""STEP 04. 화이트보드 이미지 생성 (OpenAI Image API → PNG).

그림체 일관성: 모든 장면에 같은 스타일 프리셋 문구 + 같은 반복 시각 요소(visual_motif) 묘사를 붙인다.
장면별로 독립이라 병렬로 생성한다.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from ..config import PROMPTS_DIR
from ..images import get_image_provider, postprocess
from ..utils.retry import retry


def load_style(preset: str) -> dict:
    styles = json.loads((PROMPTS_DIR / "styles.json").read_text(encoding="utf-8"))
    if preset not in styles:
        raise ValueError(f"스타일 프리셋 '{preset}' 없음. 사용 가능: {', '.join(styles)}")
    return styles[preset]


def compose_prompt(style_prompt: str, scene_prompt: str, motif: str) -> str:
    parts = [style_prompt, f"Scene: {scene_prompt.strip()}"]
    if motif:
        parts.append(f"Whenever {motif} appears, draw it exactly the same way as in every other scene of this series.")
    return "\n".join(parts)


def run(job) -> None:
    doc = job.doc()
    style = load_style(doc.style_preset or job.settings.style_preset)
    provider = get_image_provider(job.settings.image_provider)
    targets = [s for s in doc.scenes if job.wants(s.id)]

    def one(scene):
        out = job.path(f"assets/images/scene_{scene.id:02d}.png")
        motif = doc.visual_motif if style.get("use_motif", True) else ""
        prompt = compose_prompt(style["prompt"], scene.image_prompt, motif)
        if provider.name == "placeholder":
            provider.generate(scene.image_prompt, out, caption=scene.caption, index=scene.id)
        else:
            retry(lambda: provider.generate(prompt, out), attempts=3, log=job.log, what=f"이미지 장면 {scene.id}")
        pp = style.get("postprocess", {})
        postprocess(out, pp.get("grayscale", False), pp.get("white_threshold", 0))
        job.log.info("STEP04: 장면 %d 이미지 저장 (%s)", scene.id, provider.label)
        return prompt

    with ThreadPoolExecutor(max_workers=3) as ex:
        prompts = list(ex.map(one, targets))
    job.merge_scenes({s.id: {"image": f"assets/images/scene_{s.id:02d}.png"} for s in targets},
                     meta={"image_model": provider.label})
    (job.dir / "image_prompts.json").write_text(
        json.dumps({s.id: p for s, p in zip(targets, prompts)}, ensure_ascii=False, indent=2), encoding="utf-8")
    unit = provider.cost_per_image()
    prev = job.metrics["cost"].get("image", {})
    count = prev.get("images", 0) + len(targets)
    job.add_cost("image", {"model": provider.label, "images": count,
                           "cost_usd": None if unit is None else round(unit * count, 4)})
