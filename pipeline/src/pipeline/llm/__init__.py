"""LLM 어댑터. EXAONE·OpenAI 모두 OpenAI 호환 Chat Completions 라서 클래스 하나로 처리한다.

LLM_PROVIDER=openai(기본) | exaone 로 바꾼다. 호출마다 토큰 사용량을 모아 비용 측정에 쓴다.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field

from ..config import env
from ..utils.jsonx import extract_json

# 1M 토큰당 USD (입력, 출력). 공식 가격표가 없는 모델은 None → 비용 '미확인'으로 표시.
PRICES: dict[str, tuple[float, float] | None] = {
    "k-exaone_v2.5": None,
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4o-mini": (0.15, 0.60),
}


# 호출 시작 간격(초). EXAONE 은 초당 1회 한도(429 "second limit(1)")가 있어 프로세스 전체에서 간격을 둔다.
MIN_INTERVAL = {"exaone": 1.2, "openai": 0.0}
_rate_lock = threading.Lock()
_last_call: dict[str, float] = {}


def _rate_wait(provider: str) -> None:
    gap = MIN_INTERVAL.get(provider, 0.0)
    if not gap:
        return
    with _rate_lock:
        wait = _last_call.get(provider, 0.0) + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_call[provider] = time.time()


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    seconds: float = 0.0
    log: list[dict] = field(default_factory=list)

    def cost_usd(self, model: str) -> float | None:
        p = PRICES.get(model)
        if p is None:
            return None
        return round(self.prompt_tokens / 1e6 * p[0] + self.completion_tokens / 1e6 * p[1], 5)


class LLM:
    def __init__(self, provider: str | None = None):
        self.provider = (provider or env("LLM_PROVIDER", "openai")).lower()
        if self.provider == "exaone":
            self.base_url = env("EXAONE_BASE_URL", "https://api.exaone.ai/v1")
            self.api_key = env("EXAONE_API_KEY")
            self.model = env("EXAONE_MODEL", "k-exaone_v2.5")
            self.effort = env("EXAONE_EFFORT", "low")  # 공식 값: low / high / max
            key_name = "EXAONE_API_KEY"
        elif self.provider == "openai":
            self.base_url = env("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.api_key = env("OPENAI_API_KEY")
            self.model = env("OPENAI_MODEL", "gpt-4.1-mini")
            self.effort = ""
            key_name = "OPENAI_API_KEY"
        else:
            raise ValueError(f"알 수 없는 LLM_PROVIDER: {self.provider} (exaone | openai)")
        if not self.api_key:
            raise RuntimeError(f"{key_name} 가 설정되지 않았습니다 (LLM_PROVIDER={self.provider}).")
        from openai import OpenAI

        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=3, timeout=300)
        self.usage = Usage()

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    def chat(self, messages: list[dict], *, temperature: float | None = None, max_tokens: int = 16000,
             effort: str | None = None, tag: str = "") -> str:
        kwargs: dict = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        if self.provider == "exaone":
            kwargs["temperature"] = 1.0 if temperature is None else temperature
            kwargs["top_p"] = 0.95
            kwargs["extra_body"] = {"reasoning_effort": effort or self.effort}
        elif temperature is not None:
            kwargs["temperature"] = temperature
        _rate_wait(self.provider)
        t = time.time()
        r = self.client.chat.completions.create(**kwargs)
        dt = time.time() - t
        u = r.usage
        rt = getattr(u, "reasoning_tokens", 0) or 0
        self.usage.calls += 1
        self.usage.prompt_tokens += u.prompt_tokens if u else 0
        self.usage.completion_tokens += u.completion_tokens if u else 0
        self.usage.reasoning_tokens += rt
        self.usage.seconds += dt
        self.usage.log.append({"tag": tag, "seconds": round(dt, 1),
                               "prompt_tokens": u.prompt_tokens if u else 0,
                               "completion_tokens": u.completion_tokens if u else 0})
        return (r.choices[0].message.content or "").strip()

    def chat_json(self, messages: list[dict], **kw):
        """JSON 이 깨져 오면 한 번 더 요청한다(리스크 대응: 제한적 재시도)."""
        text = self.chat(messages, **kw)
        try:
            return extract_json(text)
        except (ValueError, json.JSONDecodeError) as e:
            retry_msgs = messages + [
                {"role": "assistant", "content": text[-4000:]},
                {"role": "user", "content": f"JSON 형식이 올바르지 않습니다({str(e)[:120]}). 설명 없이 올바른 JSON 하나만 다시 출력하세요."},
            ]
            return extract_json(self.chat(retry_msgs, **{**kw, "tag": kw.get("tag", "") + "_json_retry"}))

    def summary(self) -> dict:
        return {
            "model": self.label,
            "calls": self.usage.calls,
            "prompt_tokens": self.usage.prompt_tokens,
            "completion_tokens": self.usage.completion_tokens,
            "reasoning_tokens": self.usage.reasoning_tokens,
            "seconds": round(self.usage.seconds, 1),
            "cost_usd": self.usage.cost_usd(self.model),
        }
