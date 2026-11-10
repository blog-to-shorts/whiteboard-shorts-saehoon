import { useCallback, useEffect, useState } from "react";
import { api, type JobStatus } from "./api";
import { NewJob } from "./components/NewJob";
import { JobList } from "./components/JobList";
import { JobDetail } from "./components/JobDetail";
import { EvalPanel } from "./components/EvalPanel";

type Tab = "studio" | "eval";

export function App() {
  const [tab, setTab] = useState<Tab>("studio");
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [apiDown, setApiDown] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listJobs();
      setJobs(list);
      setApiDown(false);
      setSelected((cur) => cur ?? list.find((j) => j.video_url)?.id ?? list[0]?.id ?? null);
    } catch {
      setApiDown(true);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="logo" aria-hidden>
            <svg viewBox="0 0 32 32" width="34" height="34">
              <rect x="3" y="3" width="26" height="26" rx="5" fill="#fff" stroke="currentColor" strokeWidth="2.5" />
              <path d="M9 21 L15 11 L19 17 L23 13" fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
            </svg>
          </span>
          <div>
            <h1>화이트보드 숏폼 스튜디오</h1>
            <p>블로그 글 → AI 대본 → 화이트보드 그림 → 드로잉·내레이션·자막 → 9:16 영상</p>
          </div>
        </div>
        <nav className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "studio"} className={tab === "studio" ? "on" : ""} onClick={() => setTab("studio")}>
            영상 만들기
          </button>
          <button role="tab" aria-selected={tab === "eval"} className={tab === "eval" ? "on" : ""} onClick={() => setTab("eval")}>
            품질 평가
          </button>
        </nav>
      </header>

      {apiDown && (
        <div className="banner err">
          API 서버에 연결할 수 없어요. <code>uv run uvicorn app.main:app --app-dir backend --port 8000</code> 로 백엔드를 켜 주세요.
        </div>
      )}

      {tab === "studio" ? (
        <main className="grid">
          <aside className="col-left">
            <NewJob
              onCreated={(id) => {
                setSelected(id);
                refresh();
              }}
            />
            <JobList jobs={jobs} selected={selected} onSelect={setSelected} />
          </aside>
          <section className="col-right">
            {selected ? (
              <JobDetail key={selected} jobId={selected} onChanged={refresh} />
            ) : (
              <div className="card empty">왼쪽에서 블로그 URL을 넣고 영상을 만들어 보세요.</div>
            )}
          </section>
        </main>
      ) : (
        <main>
          <EvalPanel />
        </main>
      )}
      <footer className="foot">
        FastAPI · Python AI Pipeline · whiteboard-animator · Remotion · <a href="/docs">API 문서</a>
      </footer>
    </div>
  );
}
