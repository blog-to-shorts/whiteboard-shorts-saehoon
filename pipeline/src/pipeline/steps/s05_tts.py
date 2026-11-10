"""STEP 05. 한국어 TTS 생성 → 장면별 음성 + 단어 타이밍 + 실제 길이(duration) 기록.

리스크 대응(TTS 길이 편차): 전체가 60초를 넘으면 Edge 말 속도를 한 번 올려 다시 만든다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..checks import LIMITS, SCENE_PAD_SEC
from ..schema import Word
from ..tts import get_tts
from ..utils.ffmpeg import probe_duration
from ..utils.retry import retry


def _synth_all(job, doc, tts, targets):
    def one(scene):
        out = job.path(f"assets/audio/scene_{scene.id:02d}.mp3")
        words = retry(lambda: tts.synthesize(scene.narration, out), attempts=3, log=job.log, what=f"TTS 장면 {scene.id}")
        scene.audio = job.rel(out)
        scene.duration = round(probe_duration(out), 3)
        scene.words = [Word(**w) for w in words]
        return scene

    # ElevenLabs 무료·Starter 플랜은 동시 요청 2개 제한(429 concurrent_limit_exceeded)
    workers = 2 if tts.name == "elevenlabs" else 3
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, targets))


def total_seconds(doc) -> float:
    return sum((s.duration or 0) + SCENE_PAD_SEC for s in doc.scenes)


def run(job) -> None:
    doc = job.doc()
    tts = get_tts(job.settings.tts_provider)
    targets = [s for s in doc.scenes if job.wants(s.id)]
    _synth_all(job, doc, tts, targets)
    total = total_seconds(doc)
    if total > LIMITS.max_sec and tts.name == "edge" and job.only_scenes is None:
        pct = min(35, int((total / (LIMITS.max_sec - 2) - 1) * 100) + 8 + 5)
        job.log.warning("STEP05: 음성 합계 %.1f초 > %ds → 말 속도 +%d%% 로 다시 생성", total, LIMITS.max_sec, pct)
        tts = get_tts("edge", rate=f"+{pct}%")
        _synth_all(job, doc, tts, doc.scenes)
        total = total_seconds(doc)
    job.merge_scenes(
        {s.id: {"audio": s.audio, "duration": s.duration, "words": s.words} for s in doc.scenes if s.audio},
        meta={"tts": tts.label, "voice_seconds": round(total, 1)},
    )
    chars = sum(len(s.narration) for s in doc.scenes)
    job.add_cost("tts", {"model": tts.label, "chars": chars, "cost_usd": 0.0 if tts.name == "edge" else None})
    job.log.info("STEP05: 음성 %d개, 합계 %.1f초 (%s)", len(targets), total, tts.label)
