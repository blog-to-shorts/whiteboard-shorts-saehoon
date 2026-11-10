// pipeline/steps/s08_render.py 가 만드는 props 와 같은 구조
export type Cue = { text: string; start: number; end: number };

export type SceneProps = {
  id: number;
  caption: string;
  video: string | null; // jobs/<id>/ 기준 상대경로 (--public-dir 로 서빙)
  image: string | null;
  audio: string | null;
  duration: number; // 실제 음성 길이(초)
  cues: Cue[];
};

export type VideoProps = {
  title: string;
  hook: string;
  sourceUrl: string;
  fps: number;
  padSec: number; // 장면 끝 여백(초)
  accent: string;
  scenes: SceneProps[];
};

export const sceneFrames = (s: SceneProps, fps: number, padSec: number) =>
  Math.max(1, Math.ceil((s.duration + padSec) * fps));
