import { useState } from "react";
import FilterableTable from "./FilterableTable";
import Markdown from "./Markdown";

function TableSkeleton() {
  return (
    <div className="skeleton">
      <div className="skeleton-row skeleton-controls" />
      {Array.from({ length: 6 }, (_, i) => (
        <div className="skeleton-row" key={i} style={{ animationDelay: `${i * 60}ms` }} />
      ))}
    </div>
  );
}

function InsightSkeleton() {
  return (
    <div className="skeleton">
      {Array.from({ length: 8 }, (_, i) => (
        <div className="skeleton-row" key={i} style={{ animationDelay: `${i * 60}ms`, height: 14 }} />
      ))}
    </div>
  );
}

function formatTimestamp(iso) {
  if (!iso) return "never";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function AgentPanel({ agent, table, stats }) {
  const [showInsight, setShowInsight] = useState(false);

  return (
    <div className={`panel-layout ${showInsight ? "panel-layout-expanded" : ""}`}>
      <div className="panel-main">
        <div className="panel-status-row">
          {agent && (
            <>
              <span className={`badge ${agent.ok ? "badge-ok" : "badge-error"}`}>{agent.ok ? "OK" : "ERROR"}</span>
              <span className="panel-meta">Updated {formatTimestamp(agent.generated_at)}</span>
            </>
          )}
          {!showInsight && (
            <button type="button" className="panel-side-toggle-floating" onClick={() => setShowInsight(true)}>
              <span className="panel-side-title">✦ AI Insight</span>
              <span className="panel-side-caret">Show ▼</span>
            </button>
          )}
        </div>

        {stats && stats.length > 0 && (
          <div className="stat-strip">
            {stats.map((s) => (
              <div key={s.label} className={`stat-card stat-${s.tone ?? "gray"}`}>
                <span className="stat-value">{s.value}</span>
                <span className="stat-label">{s.label}</span>
              </div>
            ))}
          </div>
        )}

        {table ? <FilterableTable {...table} /> : <TableSkeleton />}
      </div>

      {showInsight && (
        <aside className="panel-side">
          <button type="button" className="panel-side-toggle" onClick={() => setShowInsight(false)}>
            <span className="panel-side-title">✦ AI Insight</span>
            <span className="panel-side-caret">Hide ▲</span>
          </button>
          {agent && <span className="panel-meta panel-side-timestamp">{formatTimestamp(agent.generated_at)}</span>}
          <div className="panel-side-body">{agent ? <Markdown text={agent.text} /> : <InsightSkeleton />}</div>
        </aside>
      )}
    </div>
  );
}
