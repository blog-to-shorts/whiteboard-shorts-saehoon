"""STEP 07. 자막(SRT) 생성 및 영상 전처리(FFmpeg H.264 변환).

- 장면별 SRT(assets/subtitles/scene_XX.srt) + 전체 SRT(subtitles.srt, 최종 영상 시간축)
- 드로잉 영상을 Remotion 호환 H.264/yuv420p/고정 fps 로 변환 → videos/scene_XX.mp4
"""

from __future__ import annotations

from ..checks import SCENE_PAD_SEC
from ..schema import Cue
from ..subtitles import to_srt, words_to_cues
from ..utils.ffmpeg import to_h264


def run(job) -> None:
    doc = job.doc()
    offset, index, full = 0.0, 1, []
    for s in doc.scenes:
        if job.wants(s.id) or not s.cues:
            cues = words_to_cues([w.model_dump() for w in s.words], s.narration, s.duration or 0)
            s.cues = [Cue(**c) for c in cues]
            srt = job.path(f"assets/subtitles/scene_{s.id:02d}.srt")
            srt.write_text(to_srt(cues), encoding="utf-8")
            s.subtitle = job.rel(srt)
        cues = [c.model_dump() for c in s.cues]
        full.append(to_srt(cues, offset=offset, start_index=index))
        index += len(cues)
        offset += (s.duration or 0) + SCENE_PAD_SEC
        if job.wants(s.id) and s.video:
            raw = job.dir / s.video
            dst = job.path(f"videos/scene_{s.id:02d}.mp4")
            to_h264(raw, dst, fps=doc.fps)
            s.video = job.rel(dst)
    (job.dir / "subtitles.srt").write_text("\n".join(full), encoding="utf-8")
    job.save_doc(doc)
    job.log.info("STEP07: 자막 큐 %d개, 전체 %.1f초, 장면 영상 H.264 변환", index - 1, offset)
