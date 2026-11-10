// FastAPI 백엔드 호출. 타입은 backend/app/models.py · pipeline/schema.py 와 같은 구조.

export type StepInfo = { name: string; seconds: number; ok: boolean; error?: string };

export type JobStatus = {
  id: string;
  state: "queued" | "running" | "done" | "partial" | "failed" | "seeded" | string;
  step: number | null;
  step_name: string | null;
  error: string | null;
  total_seconds: number | null;
  video_url: string | null;
  updated_at: number | null;
  title: string | null;
  thumbnail_url: string | null;
  video_seconds: number | null;
  steps_done: Record<string, StepInfo>;
};

export type Cue = { text: string; start: number; end: number };
export type Scene = {
  id: number;
  caption: string;
  narration: string;
  image_prompt: string;
  source: string[];
  image: string | null;
  audio: string | null;
  video: string | null;
  duration: number | null;
  cues: Cue[];
};
export type ScenesDoc = {
  title: string;
  hook: string;
  source_url: string;
  style_preset: string;
  visual_motif: string;
  scenes: Scene[];
  meta: Record<string, any>;
};

export type JobOptions = {
  llm?: "exaone" | "openai";
  image?: "openai" | "placeholder";
  tts?: "edge" | "elevenlabs";
  animator?: "whiteboard" | "simple";
  style?: string;
  prompt_version?: "v1" | "v2";
  scene_count: number;
  target_duration: number;
};

export type Quality = {
  video_seconds: number | null;
  duration_ok: boolean;
  voice_seconds: number | null;
  subtitle_max_drift_sec: number | null;
  subtitle_within_video: boolean;
  generation_seconds: number | null;
  step_seconds: Record<string, number>;
  cost_usd: number | null;
  cost_detail: Record<string, any>;
  animator: string | null;
  edited: boolean;
  style?: { score: number; checks: Record<string, boolean>; cv: Record<string, number> };
};

export type EvalSummary = {
  run?: string;
  script?: Record<string, Record<string, number | null>>;
  samples?: string[];
  errors?: string[];
  images?: { sample: string; style: string; score: number; cv_stroke: number; text_area: number | null }[];
};

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* 본문 없음 */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => req<{ ok: boolean; keys: Record<string, boolean> }>("/api/health"),
  listJobs: () => req<JobStatus[]>("/api/jobs?limit=40"),
  getJob: (id: string) => req<JobStatus>(`/api/jobs/${id}`),
  createJob: (body: { url?: string; text?: string; title?: string; options: JobOptions }) =>
    req<JobStatus>("/api/jobs", json(body)),
  getScenes: (id: string) => req<ScenesDoc>(`/api/jobs/${id}/scenes`),
  getQuality: (id: string) => req<Quality>(`/api/jobs/${id}/quality`),
  getLog: (id: string) => fetch(`/api/jobs/${id}/log?tail=12`).then((r) => r.text()),
  rerun: (id: string, body: { from_step: number; scenes?: number[]; edits: Partial<Scene>[] }) =>
    req<JobStatus>(`/api/jobs/${id}/rerun`, json(body)),
  evalSummary: () => req<EvalSummary>("/api/eval/summary"),
  file: (id: string, rel: string) => `/api/jobs/${id}/files/${rel}`,
};

export const STEPS: [number, string, string][] = [
  [1, "본문 추출", "Requests + BeautifulSoup"],
  [2, "콘텐츠 분석", "LLM"],
  [3, "대본·장면", "LLM + 자동 검사"],
  [4, "화이트보드 이미지", "OpenAI Image"],
  [5, "TTS", "Edge · ElevenLabs"],
  [6, "드로잉", "whiteboard-animator"],
  [7, "자막·전처리", "SRT · FFmpeg"],
  [8, "최종 합성", "Remotion"],
];
