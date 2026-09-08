import { useEffect, useState } from "react";
import AgentPanel from "./AgentPanel";
import { getLatestPanels, getLatestScan, refreshPanels } from "./api";
import {
  bottleneckDetectorColumns,
  bottleneckStats,
  flattenStandupEngineers,
  reviewNudgerColumns,
  reviewNudgerStats,
  standupStats,
  standupWriterColumns,
  ticketWatcherColumns,
  ticketWatcherStats,
} from "./panels";
import PersonalStandup from "./PersonalStandup";
import StandupHistory from "./StandupHistory";
import Tabs from "./Tabs";
import "./App.css";

// Only these 4 tabs need the (fairly heavy) combined /scan + /panels fetch --
// Standup History has its own independent, on-demand data source.
const DATA_TAB_KEYS = ["ticket_watcher", "bottleneck_detector", "review_nudger", "standup_writer"];

// Every agent's `text` is JSON (see each agents/*/agent.py's output_schema).
// A stale cache from before that agent's schema shipped would still be
// markdown prose, so this falls back to null rather than crashing -- the
// panel then just shows nothing extra until a fresh /scan repopulates it.
function parseFindings(agentResult) {
  if (!agentResult?.ok) return null;
  try {
    return JSON.parse(agentResult.text).findings ?? null;
  } catch {
    return null;
  }
}

function App() {
  const [scan, setScan] = useState(null);
  const [panels, setPanels] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("ticket_watcher");

  // Reads the Firestore-cached /panels/latest (instant) rather than hitting
  // BigQuery live -- falls back to a live refresh only the very first time
  // nothing has been cached yet.
  async function loadCached() {
    setLoading(true);
    setError(null);
    try {
      const [scanData, panelsData] = await Promise.all([
        getLatestScan(),
        getLatestPanels().catch((err) => {
          if (err.message.startsWith("404")) return refreshPanels();
          throw err;
        }),
      ]);
      setScan(scanData);
      setPanels(panelsData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Explicit refresh re-runs the live BigQuery reads (~3s) so the tables
  // reflect current data, then re-caches. Never triggers a live agent scan
  // (that's ~6.5 min) -- the AI summaries stay whatever was last cached.
  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [scanData, panelsData] = await Promise.all([getLatestScan(), refreshPanels()]);
      setScan(scanData);
      setPanels(panelsData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Lazy load: only fetch once the user is actually looking at a tab that
  // needs this data, not unconditionally on page load -- landing on (or
  // switching straight to) Standup History never pays for it.
  useEffect(() => {
    if (DATA_TAB_KEYS.includes(activeTab) && panels === null && !loading) {
      loadCached();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const tabs = [
    {
      key: "ticket_watcher",
      label: "Ticket Watcher",
      render: () => (
        <AgentPanel
          agent={scan?.agents?.ticket_watcher}
          stats={panels && ticketWatcherStats(panels.ticket_watcher.counts)}
          findings={parseFindings(scan?.agents?.ticket_watcher)}
          table={
            panels && {
              rows: panels.ticket_watcher.tickets,
              columns: ticketWatcherColumns(),
              filters: [
                { key: "team", label: "Team" },
                { key: "flag_reason", label: "Reason" },
              ],
              searchKeys: ["ticket_id", "title", "assigned_to"],
              defaultSort: { key: "priority", direction: "asc" },
              rowKey: "ticket_id",
            }
          }
        />
      ),
    },
    {
      key: "bottleneck_detector",
      label: "Bottleneck Detector",
      render: () => {
        const bottleneckFindings = parseFindings(scan?.agents?.bottleneck_detector);
        const missProbabilityByTicket = Object.fromEntries(
          (bottleneckFindings ?? []).map((f) => [f.ticket_id, f.miss_probability])
        );
        const bottleneckRows = panels?.bottleneck_detector.tickets.map((t) => ({
          ...t,
          miss_probability: missProbabilityByTicket[t.ticket_id],
        }));
        return (
        <AgentPanel
          agent={scan?.agents?.bottleneck_detector}
          stats={panels && bottleneckStats(panels.bottleneck_detector.tickets)}
          findings={bottleneckFindings}
          table={
            bottleneckRows && {
              rows: bottleneckRows,
              columns: bottleneckDetectorColumns(),
              filters: [
                { key: "team", label: "Team" },
                { key: "work_item_type", label: "Type" },
                { key: "state", label: "State" },
              ],
              searchKeys: ["ticket_id", "title", "tags"],
              defaultSort: { key: "priority", direction: "asc" },
              rowKey: "ticket_id",
            }
          }
        />
        );
      },
    },
    {
      key: "review_nudger",
      label: "Review Nudger",
      render: () => (
        <AgentPanel
          agent={scan?.agents?.review_nudger}
          stats={panels && reviewNudgerStats(panels.review_nudger.reviews)}
          findings={parseFindings(scan?.agents?.review_nudger)}
          table={
            panels && {
              rows: panels.review_nudger.reviews,
              columns: reviewNudgerColumns(),
              filters: [
                { key: "team", label: "Team" },
                { key: "reviewer", label: "Reviewer" },
              ],
              searchKeys: ["pr_id", "ticket_id", "author", "reviewer"],
              defaultSort: { key: "hours_waiting", direction: "desc" },
              rowKey: "pr_id",
            }
          }
        />
      ),
    },
    {
      key: "standup_writer",
      label: "Standup Writer",
      render: () => {
        const rows = panels && flattenStandupEngineers(panels.standup_writer.engineers);
        return (
          <>
            <PersonalStandup />
            <AgentPanel
              agent={scan?.agents?.standup_writer}
              stats={rows && standupStats(rows)}
              findings={parseFindings(scan?.agents?.standup_writer)}
              table={
                rows && {
                  rows,
                  columns: standupWriterColumns(),
                  filters: [
                    { key: "engineer", label: "Engineer" },
                    { key: "bucket", label: "Status" },
                  ],
                  searchKeys: ["ticket_id", "title"],
                  defaultSort: { key: "engineer", direction: "asc" },
                }
              }
            />
          </>
        );
      },
    },
    {
      key: "standup_history",
      label: "Standup History",
      render: () => <StandupHistory />,
    },
  ];

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark">F</div>
          <div>
            <h1>FlowMate</h1>
            <p className="app-subtitle">Live ticket/PR data plus each agent's take on it.</p>
          </div>
        </div>
        <button
          type="button"
          className={`refresh-button ${loading ? "is-loading" : ""}`}
          onClick={refresh}
          disabled={loading}
        >
          <span className="refresh-icon">⟳</span>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {error && (
        <p className="error-text">
          Could not load dashboard data: {error}. Is the API running, and has <code>POST /scan</code> been
          run at least once?
        </p>
      )}

      <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} />
    </div>
  );
}

export default App;
