"""STEP 02. AI 콘텐츠 분석: 핵심 메시지·핵심 내용·바뀌면 안 되는 사실·반복 시각 요소."""

from __future__ import annotations

from ..config import PROMPTS_DIR
from ..schema import Analysis, save_json

MAX_TEXT = 20000


def analyze(llm, title: str, text: str) -> Analysis:
    prompt = (PROMPTS_DIR / "analyze_v1.md").read_text(encoding="utf-8")
    prompt = prompt.replace("{title}", title).replace("{text}", text[:MAX_TEXT])
    data = llm.chat_json([{"role": "user", "content": prompt}], tag="analyze")
    return Analysis.model_validate(data)


def run(job) -> None:
    src = job.source()
    a = analyze(job.llm, src.title, src.text)
    save_json(job.dir / "analysis.json", a)
    job.log.info("STEP02: 핵심 '%s' / 핵심 내용 %d개 / 사실 %d개 / 모티프 '%s'",
                 a.core_message, len(a.key_points), len(a.facts), a.visual_motif)
