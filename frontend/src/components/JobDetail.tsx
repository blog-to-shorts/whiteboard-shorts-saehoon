import { useCallback, useEffect, useRef, useState } from "react";
import { api, STEPS, type JobStatus, type Quality, type ScenesDoc } from "../api";
import { SceneEditor } from "./SceneEditor";

const ACTIVE = new Set(["queued", "running"]);

export function JobDetail({ jobId, onChanged }: { jobId: string; onChanged: () => void }) {
  const [st, setSt] = useState<JobStatus | null>(null);
  const [doc, setDoc] = useState<ScenesDoc | null>(null);
  const [q, setQ] = useState<Quality | null>(null);
  const [log, setLog] = useState("");
  const lastState = useRef<string>("");

  const load = useCallback(async () => {
    const s = await api.getJob(jobId);
    setSt(s);
    if (ACTIVE.has(s.state)) setLog(await api.getLog(jobId));
    const changed = lastState.current !== `${s.state}:${s.step}:${s.updated_at}`;
    lastState.current = `${s.state}:${s.step}:${s.updated_at}`;
    if (changed) {
      api.getScenes(jobId).then(setDoc).catch(() => setDoc(null));
      if (s.video_url && !ACTIVE.has(s.state)) api.getQuality(jobId).then(setQ).catch(() => setQ(null));
      if (!ACTIVE.has(s.state)) onChanged();
    }
    return s;
  }, [jobId, onChanged]);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const s = await load();
        if (alive) timer = setTimeout(tick, ACTIVE.has(s.state) ? 2000 : 15000);
      } catch {
        if (alive) timer = setTimeout(tick, 5000);
      }
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [load]);

  if (!st) return <div className="card">불러오는 중…</div>;
  const running = ACTIVE.has(st.state);

  return (
    <div className="detail">
      <div className="card">
        <div className="detail-head">
          <div>
            <h2>{st.title || st.id}</h2>
            {doc?.source_url && (
              <a className="src" href={doc.source_url} target="_blank" rel="noreferrer">
                원문 보기 ↗
              </a>
            )}
          </div>
          {st.total_seconds != null && !running && <span className="time">생성 {fmtSec(st.total_seconds)}</span>}
        </div>
        <Pipeline st={st} reused={Boolean(doc?.meta?.seeded_from)} />
        {st.state === "failed" && <p className="msg err">실패: {st.error}</p>}
        {running && log && <pre className="log">{log}</pre>}
      </div>

      {(st.video_url || doc) && (
        <div className="result">
          <div className="card phone-card">
            {st.video_url ? (
              <>
                <video className="phone" src={st.video_url} controls playsInline poster={st.thumbnail_url ?? undefined} />
                <a className="btn" href={st.video_url} download={`${st.id}.mp4`}>
                  MP4 다운로드
                </a>
              </>
            ) : (
              <div className="phone placeholder">영상 만드는 중…</div>
            )}
          </div>
          {q && <QualityCard q={q} />}
        </div>
      )}

      {doc && <SceneEditor jobId={jobId} doc={doc} disabled={running} version={st.updated_at ?? 0} onRerun={load} />}
    </div>
  );
}

function Pipeline({ st, reused }: { st: JobStatus; reused: boolean }) {
  return (
    <ol className="pipe">
      {STEPS.map(([n, name, tech]) => {
        const done = st.steps_done[String(n)];
        const skipped = !done && reused && n <= 3; // 평가에서 만든 대본을 재사용한 작업
        const running = (st.state === "running" || st.state === "queued") && !done?.ok && isCurrent(st, n);
        const cls = done?.ok ? "ok" : done && !done.ok ? "fail" : running ? "run" : skipped ? "skip" : "";
        return (
          <li key={n} className={cls} title={done?.error || (skipped ? "품질 평가에서 만든 대본을 재사용" : tech)}>
            <span className="n">{String(n).padStart(2, "0")}</span>
            <span className="nm">{name}</span>
            <span className="tc">{done ? fmtSec(done.seconds) : skipped ? "평가 대본 재사용" : tech}</span>
          </li>
        );
      })}
    </ol>
  );
}

function isCurrent(st: JobStatus, n: number) {
  if (st.step == null) return false;
  if (st.step === 4 && (n === 4 || n === 5)) return true; // 04·05 병렬
  return st.step === n;
}

function QualityCard({ q }: { q: Quality }) {
  const rows: [string, string, boolean | null][] = [
    ["영상 길이", q.video_seconds ? `${q.video_seconds.toFixed(1)}초` : "-", q.duration_ok],
    ["자막 싱크 오차", q.subtitle_max_drift_sec != null ? `${q.subtitle_max_drift_sec.toFixed(2)}초` : "-",
      q.subtitle_max_drift_sec != null ? q.subtitle_max_drift_sec <= 0.1 : null],
    ["그림체 일관성", q.style ? `${Math.round(q.style.score * 100)}%` : "-", q.style ? q.style.score >= 0.8 : null],
    ["드로잉 엔진", q.animator ?? "-", q.animator === "whiteboard"],
    ["생성 시간", q.generation_seconds ? fmtSec(q.generation_seconds) : "-", null],
    ["비용", q.cost_usd != null ? `$${q.cost_usd}` : "미확인(단가 미공개 모델)", null],
  ];
  return (
    <div className="card quality">
      <h3>품질 지표</h3>
      <table>
        <tbody>
          {rows.map(([k, v, ok]) => (
            <tr key={k}>
              <th>{k}</th>
              <td>{v}</td>
              <td className="mark">{ok == null ? "" : ok ? "✓" : "✗"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {q.style && (
        <details>
          <summary>그림체 세부 항목</summary>
          <ul className="checks">
            {Object.entries(q.style.checks).map(([k, v]) => (
              <li key={k} className={v ? "ok" : "no"}>
                {v ? "✓" : "✗"} {k}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export function fmtSec(s: number) {
  if (s < 60) return `${s.toFixed(1)}초`;
  return `${Math.floor(s / 60)}분 ${Math.round(s % 60)}초`;
}
