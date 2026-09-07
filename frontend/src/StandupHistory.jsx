import { useEffect, useState } from "react";
import { getEngineers, getStandupHistory } from "./api";
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
  const [engineers, setEngineers] = useState(null);
  const [engineersError, setEngineersError] = useState(null);
  const [engineer, setEngineer] = useState("");
  const [start, setStart] = useState(weekAgoIso());
  const [end, setEnd] = useState(todayIso());
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getEngineers()
      .then(setEngineers)
      .catch((err) => setEngineersError(err.message));
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!engineer) return;
    setLoading(true);
    setError(null);
    try {
      const days = await getStandupHistory(engineer, start, end);
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
        <select
          value={engineer}
          onChange={(e) => setEngineer(e.target.value)}
          required
          disabled={!engineers}
        >
          <option value="" disabled>
            {engineers ? "Select engineer" : "Loading engineers..."}
          </option>
          {engineers?.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        <button type="submit" disabled={loading || !engineer}>
          {loading ? "Loading..." : "Browse"}
        </button>
      </form>

      {engineersError && <p className="error-text">Could not load engineer list: {engineersError}</p>}
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
