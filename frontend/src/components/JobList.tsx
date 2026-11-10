import type { JobStatus } from "../api";

const STATE: Record<string, string> = {
  queued: "대기",
  running: "진행 중",
  done: "완료",
  partial: "일부 완료",
  failed: "실패",
  seeded: "준비됨",
};

export function JobList({
  jobs,
  selected,
  onSelect,
}: {
  jobs: JobStatus[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="card">
      <h2>작업 목록</h2>
      {jobs.length === 0 ? (
        <p className="hint">아직 작업이 없어요.</p>
      ) : (
        <ul className="jobs">
          {jobs.map((j) => (
            <li key={j.id}>
              <button className={j.id === selected ? "job on" : "job"} onClick={() => onSelect(j.id)}>
                <span className="thumb">{j.thumbnail_url ? <img src={j.thumbnail_url} alt="" /> : null}</span>
                <span className="meta">
                  <span className="t">{j.title || j.id}</span>
                  <span className="s">
                    <span className={`pill ${j.state}`}>{STATE[j.state] ?? j.state}</span>
                    {j.video_seconds ? ` ${j.video_seconds.toFixed(1)}초` : j.state === "running" ? ` STEP ${j.step}` : ""}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
