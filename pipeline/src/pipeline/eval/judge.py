"""LLM 심사(원문 대비 대본 정확성·누락·구조·자연스러움). 개선 전·후에 같은 심사 프롬프트와 모델을 쓴다.

주의: 생성 모델과 심사 모델이 같으면 자기 평가 편향이 있을 수 있다. 보고서에 심사 모델을 함께 적는다.
"""

from __future__ import annotations

JUDGE_PROMPT = """당신은 숏폼 영상 대본 검수자입니다. 원문과 대본을 비교해 채점하세요. 관대하게 주지 말고 근거를 대세요.

[채점 기준, 각 1~5점]
- accuracy: 대본의 모든 사실(숫자·이름·장소·순서·인과)이 원문과 일치하는가. 지어낸 정보나 과장·일반화가 하나라도 있으면 3점 이하.
- coverage: 원문의 핵심 내용이 빠짐없이 들어갔는가. 가장 중요한 내용이 빠지면 2점 이하.
- structure: 첫 장면이 시청 이유(문제·상황)를 제시하고, 가운데가 순서대로 전개되고, 마지막이 결론·추천으로 끝나는가.
- naturalness: 귀로 들었을 때 자연스러운 구어체인가(글말·나열·어색한 끊김이 없는가).
- visual_fit: 각 image_prompt 가 그 장면 내레이션의 핵심을 그림으로 설명하는가.

[출력] JSON 만:
{{"accuracy":n,"coverage":n,"structure":n,"naturalness":n,"visual_fit":n,
 "distortions":["원문과 다르거나 원문에 없는 내용, 없으면 빈 배열"],
 "missing":["빠진 핵심 내용"],
 "comment":"한두 문장 총평"}}

[원문 제목] {title}
[원문]
{text}

[대본]
hook: {hook}
{scenes}
"""

KEYS = ["accuracy", "coverage", "structure", "naturalness", "visual_fit"]


def judge_script(llm, title: str, text: str, hook: str, scenes: list[dict]) -> dict:
    lines = "\n".join(
        f"장면{i}: [자막] {s.get('caption','')} [내레이션] {s.get('narration','')} [그림] {s.get('image_prompt','')}"
        for i, s in enumerate(scenes, 1)
    )
    prompt = JUDGE_PROMPT.format(title=title, text=text[:15000], hook=hook, scenes=lines)
    data = llm.chat_json([{"role": "user", "content": prompt}], temperature=0.2 if llm.provider == "openai" else None,
                         tag="judge")
    out = {k: float(data.get(k, 0) or 0) for k in KEYS}
    out["mean"] = round(sum(out[k] for k in KEYS) / len(KEYS), 2)
    out["distortions"] = data.get("distortions") or []
    out["missing"] = data.get("missing") or []
    out["comment"] = data.get("comment", "")
    return out
