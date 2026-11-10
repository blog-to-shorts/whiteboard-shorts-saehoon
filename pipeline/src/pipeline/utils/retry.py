"""제한적 재시도(리스크 대응: API 오류 → 단계별 오류 기록 및 제한적 재시도)."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry(fn: Callable[[], T], *, attempts: int = 3, base_delay: float = 2.0, log=None, what: str = "") -> T:
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — 외부 API 오류는 종류가 다양하다
            last = e
            if log:
                log.warning("%s 실패 (%d/%d): %s", what or "작업", i, attempts, str(e)[:200])
            if i < attempts:
                time.sleep(base_delay * (2 ** (i - 1)))
    assert last is not None
    raise last
