import { useState } from "react";
import { getStandupHistory } from "./api";
import FilterableTable from "./FilterableTable";
import { flattenStandupDays, standupHistoryColumns } from "./panels";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function weekAgoIso() {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}

export default function StandupHistory() {
  const [engineer, setEngineer] = useState("");
  const [start, setStart] = useState(weekAgoIso());
  const [end, setEnd] = useState(todayIso());
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!engineer.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const days = await getStandupHistory(engineer.trim(), start, end);
      setRows(flattenStandupDays(days));
    } catch (err) {
      setError(err.message);
      setRows(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <form className="standup-form" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Engineer name"
          value={engineer}
          onChange={(e) => setEngineer(e.target.value)}
          required
        />
        <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        <button type="submit" disabled={loading}>
          {loading ? "Loading..." : "Browse"}
        </button>
      </form>

      {error && <p className="error-text">{error}</p>}

      {rows && rows.length === 0 && <p className="panel-meta">No standups found in that range.</p>}

      {rows && rows.length > 0 && (
        <FilterableTable
          rows={rows}
          columns={standupHistoryColumns()}
          filters={[
            { key: "date", label: "Date" },
            { key: "bucket", label: "Status" },
          ]}
          searchKeys={["ticket_id", "title"]}
          defaultSort={{ key: "date", direction: "asc" }}
        />
      )}
    </div>
  );
}
