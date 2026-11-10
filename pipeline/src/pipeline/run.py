"""파이프라인 오케스트레이터: 입력 한 번으로 STEP 01~08 → final.mp4.

사용 예
  wbs run --url https://blog.naver.com/xxx/123
  wbs run --text-file post.txt --title "제목"
  wbs run --job <id> --from 4 --scenes 2        # 장면 2 이미지만 다시 만들고 이후 단계 재실행
  wbs run --job <id> --from 3 --prompt-version v1

설계 포인트: STEP 04(이미지)와 05(TTS)는 서로 독립이라 동시에 실행한다. 06 은 둘 다 끝난 뒤 시작한다.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from .config import Settings
from .context import STEP_NAMES, Job
from .steps import (s01_extract, s02_analyze, s03_script, s04_image, s05_tts, s06_animate, s07_subtitle,
                    s08_render)

STEPS = {2: s02_analyze.run, 3: s03_script.run, 4: s04_image.run, 5: s05_tts.run,
         6: s06_animate.run, 7: s07_subtitle.run, 8: s08_render.run}


def _timed(job: Job, step: int, fn) -> None:
    job.status(state="running", step=step, step_name=STEP_NAMES[step])
    job.log.info("── STEP %02d %s", step, STEP_NAMES[step])
    t = time.time()
    try:
        fn()
    except Exception as e:
        job.record_step(step, time.time() - t, ok=False, error=str(e)[:500])
        raise
    job.record_step(step, time.time() - t, ok=True)


def run_pipeline(settings: Settings, *, url: str | None = None, text: str | None = None, title: str | None = None,
                 job_id: str | None = None, start: int = 1, end: int = 8, only_scenes: set[int] | None = None) -> Job:
    job = Job(settings, job_id, only_scenes)
    t0 = time.time()
    job.status(state="running", step=start, started_at=t0, error=None)
    try:
        if start <= 1 <= end:
            _timed(job, 1, lambda: s01_extract.run(job, url=url, text=text, title=title))
        step = max(start, 2)
        while step <= end:
            if step == 4 and end >= 5:  # 이미지·음성 병렬
                job.status(state="running", step=4, step_name="이미지 + TTS (병렬)")
                with ThreadPoolExecutor(max_workers=2) as ex:
                    futs = [ex.submit(_timed, job, 4, lambda: STEPS[4](job)),
                            ex.submit(_timed, job, 5, lambda: STEPS[5](job))]
                    errors = [f.exception() for f in futs if f.exception()]
                if errors:
                    raise errors[0]
                step = 6
                continue
            _timed(job, step, lambda s=step: STEPS[s](job))
            step += 1
    except Exception as e:
        job.status(state="failed", error=f"{type(e).__name__}: {e}"[:800])
        job.log.error("실패: %s\n%s", e, traceback.format_exc(limit=3))
        raise
    total = round(time.time() - t0, 1)
    job.metrics["total_seconds"] = total
    job.save_metrics()
    job.status(state="done" if end == 8 else "partial", step=end, total_seconds=total,
               video="final.mp4" if end == 8 else None)
    job.log.info("완료: %s (%.1f초) → %s", job.id, total, job.dir)
    return job


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wbs", description="AI 화이트보드 숏폼 자동 생성 파이프라인")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="파이프라인 실행")
    src = r.add_mutually_exclusive_group()
    src.add_argument("--url", help="블로그 URL")
    src.add_argument("--text-file", help="원문 텍스트 파일(추출 실패 시 대체 입력)")
    r.add_argument("--title", help="--text-file 사용 시 제목")
    r.add_argument("--job", help="기존 작업 ID (부분 재실행)")
    r.add_argument("--from", dest="start", type=int, default=1, help="시작 STEP (1~8)")
    r.add_argument("--to", dest="end", type=int, default=8, help="끝 STEP (1~8)")
    r.add_argument("--scenes", help="STEP 04~07 을 이 장면만 다시 (예: 2,3)")
    r.add_argument("--llm", choices=["exaone", "openai"])
    r.add_argument("--image", choices=["openai", "placeholder"])
    r.add_argument("--tts", choices=["edge", "elevenlabs"])
    r.add_argument("--animator", choices=["whiteboard", "simple"])
    r.add_argument("--style", help="스타일 프리셋 (prompts/styles.json)")
    r.add_argument("--prompt-version", choices=["v1", "v2"])
    r.add_argument("--scene-count", type=int, default=5)
    r.add_argument("--target-duration", type=int, default=45)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.cmd != "run":
        return 2
    if not (a.url or a.text_file or a.job):
        print("--url, --text-file, --job 중 하나가 필요합니다", file=sys.stderr)
        return 2
    s = Settings()
    for attr, val in [("llm_provider", a.llm), ("image_provider", a.image), ("tts_provider", a.tts),
                      ("animator", a.animator), ("style_preset", a.style), ("prompt_version", a.prompt_version)]:
        if val:
            setattr(s, attr, val)
    s.scene_count, s.target_duration = a.scene_count, a.target_duration
    text = open(a.text_file, encoding="utf-8").read() if a.text_file else None
    only = {int(x) for x in a.scenes.split(",")} if a.scenes else None
    start = a.start if (a.job or a.start > 1) else 1
    try:
        job = run_pipeline(s, url=a.url, text=text, title=a.title, job_id=a.job, start=start, end=a.end,
                           only_scenes=only)
    except Exception as e:  # noqa: BLE001
        print(f"wbs: 실패: {e}", file=sys.stderr)
        return 1
    print(job.dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
