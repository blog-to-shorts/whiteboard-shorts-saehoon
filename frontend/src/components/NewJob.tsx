import { useState } from "react";
import { api, type JobOptions } from "../api";

export function NewJob({ onCreated }: { onCreated: (id: string) => void }) {
  const [mode, setMode] = useState<"url" | "text">("url");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [opts, setOpts] = useState<JobOptions>({
    llm: "openai",
    image: "openai",
    tts: "elevenlabs",
    prompt_version: "v2",
    scene_count: 5,
    target_duration: 45,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const set = <K extends keyof JobOptions>(k: K, v: JobOptions[K]) => setOpts((o) => ({ ...o, [k]: v }));
  const canSubmit = mode === "url" ? /^https?:\/\//.test(url.trim()) : text.trim().length >= 200;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || busy) return;
    setBusy(true);
    setErr("");
    try {
      const job = await api.createJob(
        mode === "url" ? { url: url.trim(), options: opts } : { text, title: title || undefined, options: opts },
      );
      onCreated(job.id);
      setUrl("");
      setText("");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>새 영상 만들기</h2>
      <div className="seg" role="radiogroup" aria-label="입력 방식">
        <button type="button" className={mode === "url" ? "on" : ""} onClick={() => setMode("url")}>
          블로그 URL
        </button>
        <button type="button" className={mode === "text" ? "on" : ""} onClick={() => setMode("text")}>
          원문 직접 입력
        </button>
      </div>
      {mode === "url" ? (
        <label className="field">
          <span>블로그 주소</span>
          <input
            type="url"
            placeholder="https://blog.naver.com/아이디/글번호"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </label>
      ) : (
        <>
          <label className="field">
            <span>제목</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="글 제목" />
          </label>
          <label className="field">
            <span>본문 (200자 이상)</span>
            <textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} />
          </label>
        </>
      )}

      <details className="opts">
        <summary>옵션</summary>
        <div className="opt-grid">
          <label>
            대본 AI
            <select value={opts.llm} onChange={(e) => set("llm", e.target.value as JobOptions["llm"])}>
              <option value="openai">OpenAI (기본)</option>
              <option value="exaone">EXAONE</option>
            </select>
          </label>
          <label>
            목소리
            <select value={opts.tts} onChange={(e) => set("tts", e.target.value as JobOptions["tts"])}>
              <option value="elevenlabs">ElevenLabs · Alice</option>
              <option value="edge">Edge · 선희 (무료)</option>
            </select>
          </label>
          <label>
            그림
            <select value={opts.image} onChange={(e) => set("image", e.target.value as JobOptions["image"])}>
              <option value="openai">OpenAI 화이트보드</option>
              <option value="placeholder">자리표시(테스트)</option>
            </select>
          </label>
          <label>
            프롬프트
            <select
              value={opts.prompt_version}
              onChange={(e) => set("prompt_version", e.target.value as JobOptions["prompt_version"])}
            >
              <option value="v2">v2 개선 후</option>
              <option value="v1">v1 개선 전</option>
            </select>
          </label>
          <label>
            장면 수
            <input
              type="number"
              min={4}
              max={8}
              value={opts.scene_count}
              onChange={(e) => set("scene_count", Number(e.target.value))}
            />
          </label>
          <label>
            목표 길이(초)
            <input
              type="number"
              min={30}
              max={60}
              step={5}
              value={opts.target_duration}
              onChange={(e) => set("target_duration", Number(e.target.value))}
            />
          </label>
        </div>
      </details>

      {err && <p className="msg err">{err}</p>}
      <button className="primary" disabled={!canSubmit || busy}>
        {busy ? "요청 중…" : "영상 만들기"}
      </button>
      <p className="hint">요청하면 작업 화면에서 STEP 01~08 진행 상황을 볼 수 있어요. (EXAONE 대본은 1편에 수 분 걸려요.)</p>
    </form>
  );
}
