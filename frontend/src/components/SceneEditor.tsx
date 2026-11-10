import { useEffect, useMemo, useState } from "react";
import { api, type Scene, type ScenesDoc } from "../api";

type Edit = Pick<Scene, "caption" | "narration" | "image_prompt">;

// 수정 용이성: 고친 항목에 따라 필요한 단계만 다시 실행한다.
// 그림 설명 → STEP 04~(그 장면만) / 내레이션 → STEP 05~(그 장면만) / 키워드만 → STEP 08(합성만)
function plan(doc: ScenesDoc, edits: Record<number, Edit>) {
  const changed: { id: number; from: number }[] = [];
  for (const s of doc.scenes) {
    const e = edits[s.id];
    if (!e) continue;
    if (e.image_prompt !== s.image_prompt) changed.push({ id: s.id, from: 4 });
    else if (e.narration !== s.narration) changed.push({ id: s.id, from: 5 });
    else if (e.caption !== s.caption) changed.push({ id: s.id, from: 8 });
  }
  if (!changed.length) return null;
  return { from: Math.min(...changed.map((c) => c.from)), scenes: changed.map((c) => c.id) };
}

const STEP_LABEL: Record<number, string> = { 4: "그림부터", 5: "음성부터", 8: "합성만" };

export function SceneEditor({
  jobId,
  doc,
  disabled,
  version,
  onRerun,
}: {
  jobId: string;
  doc: ScenesDoc;
  disabled: boolean;
  version: number; // 재생성 후 바뀐 그림을 다시 받도록 캐시 무효화
  onRerun: () => void;
}) {
  const initial = useMemo(
    () =>
      Object.fromEntries(
        doc.scenes.map((s) => [s.id, { caption: s.caption, narration: s.narration, image_prompt: s.image_prompt }]),
      ) as Record<number, Edit>,
    [doc],
  );
  const [edits, setEdits] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => setEdits(initial), [initial]);

  const p = plan(doc, edits);
  const upd = (id: number, k: keyof Edit, v: string) => setEdits((e) => ({ ...e, [id]: { ...e[id], [k]: v } }));

  async function rerun() {
    if (!p) return;
    setBusy(true);
    setErr("");
    try {
      const changedEdits = p.scenes.map((id) => ({ id, ...edits[id] }));
      await api.rerun(jobId, { from_step: p.from, scenes: p.from < 8 ? p.scenes : undefined, edits: changedEdits });
      onRerun();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const total = doc.scenes.reduce((a, s) => a + (s.narration?.length ?? 0), 0);

  return (
    <div className="card">
      <div className="detail-head">
        <div>
          <h2>대본 · 장면</h2>
          <p className="hint">
            표지 문구 <b>{doc.hook}</b> · 장면 {doc.scenes.length}개 · 내레이션 {total}자 · 프롬프트{" "}
            {doc.meta?.prompt_version ?? "-"} · {doc.meta?.llm ?? ""}
          </p>
        </div>
        <div className="rerun">
          {p && <span className="hint">수정 {p.scenes.length}개 → {STEP_LABEL[p.from]} 다시</span>}
          <button className="primary" disabled={!p || busy || disabled} onClick={rerun}>
            {busy ? "요청 중…" : "수정 반영해 다시 만들기"}
          </button>
        </div>
      </div>
      {err && <p className="msg err">{err}</p>}
      <ol className="scenes">
        {doc.scenes.map((s) => {
          const e = edits[s.id] ?? { caption: "", narration: "", image_prompt: "" };
          const dirty = e.caption !== s.caption || e.narration !== s.narration || e.image_prompt !== s.image_prompt;
          return (
            <li key={s.id} className={dirty ? "scene dirty" : "scene"}>
              <div className="scene-img">
                {s.image ? <img src={`${api.file(jobId, s.image)}?v=${Math.round(version)}`} alt={`장면 ${s.id}`} /> : <span>그림 없음</span>}
                <span className="no">{s.id}</span>
              </div>
              <div className="scene-body">
                <label>
                  <span>
                    키워드 <em>{e.caption.length}/16</em>
                  </span>
                  <input value={e.caption} disabled={disabled} onChange={(x) => upd(s.id, "caption", x.target.value)} />
                </label>
                <label>
                  <span>
                    내레이션 <em>{e.narration.length}자{s.duration ? ` · ${s.duration.toFixed(1)}초` : ""}</em>
                  </span>
                  <textarea rows={2} value={e.narration} disabled={disabled} onChange={(x) => upd(s.id, "narration", x.target.value)} />
                </label>
                <label>
                  <span>그림 설명 (영어)</span>
                  <textarea rows={2} value={e.image_prompt} disabled={disabled} onChange={(x) => upd(s.id, "image_prompt", x.target.value)} />
                </label>
                {s.source?.length > 0 && (
                  <p className="source" title="이 장면의 근거가 된 원문 문장">
                    근거: “{s.source.join(" … ")}”
                  </p>
                )}
                {s.audio && <audio controls preload="none" src={`${api.file(jobId, s.audio)}?v=${Math.round(version)}`} />}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
