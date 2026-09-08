import { bucketPill, daysLeftPill, flagReasonPill, missRiskPill, priorityPill, statePill } from "./Pill";

function formatDate(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
}

export function ticketWatcherColumns() {
  return [
    { key: "priority", label: "Pri", render: (r) => priorityPill(r.priority) },
    { key: "ticket_id", label: "Ticket" },
    { key: "title", label: "Title" },
    { key: "team", label: "Team" },
    { key: "flag_reason", label: "Reason", render: (r) => flagReasonPill(r.flag_reason) },
    { key: "assigned_to", label: "Assignee" },
    { key: "changed_date", label: "Last changed", render: (r) => formatDate(r.changed_date) },
    { key: "blocked_reason", label: "Blocked reason" },
  ];
}

export function reviewNudgerColumns() {
  return [
    { key: "hours_waiting", label: "Hours waiting" },
    { key: "pr_id", label: "PR" },
    { key: "ticket_id", label: "Ticket" },
    { key: "author", label: "Author" },
    { key: "reviewer", label: "Reviewer" },
    { key: "team", label: "Team" },
    { key: "sprint_end_date", label: "Sprint ends", render: (r) => formatDate(r.sprint_end_date) },
  ];
}

export function bottleneckDetectorColumns() {
  return [
    { key: "priority", label: "Pri", render: (r) => priorityPill(r.priority) },
    { key: "ticket_id", label: "Ticket" },
    { key: "title", label: "Title" },
    { key: "team", label: "Team" },
    { key: "work_item_type", label: "Type" },
    { key: "state", label: "State", render: (r) => statePill(r.state) },
    { key: "tags", label: "Tags" },
    { key: "days_until_sprint_end", label: "Days left", render: (r) => daysLeftPill(r.days_until_sprint_end) },
    {
      key: "miss_probability",
      label: "Miss risk",
      // Only present for tickets Gemini actually cross-referenced and found a
      // real signal for (see agents/bottleneck_detector/agent.py) -- blank
      // for the rest, deliberately, rather than a manufactured number.
      render: (r) => missRiskPill(r.miss_probability) ?? "—",
    },
    { key: "reviewer", label: "Reviewer" },
  ];
}

export function standupWriterColumns() {
  return [
    { key: "engineer", label: "Engineer" },
    { key: "bucket", label: "Status", render: (r) => bucketPill(r.bucket) },
    { key: "ticket_id", label: "Ticket" },
    { key: "title", label: "Title" },
    { key: "priority", label: "Priority", render: (r) => priorityPill(r.priority) },
    { key: "blocked_reason", label: "Blocked reason" },
  ];
}

export function flattenStandupEngineers(engineers) {
  const rows = [];
  for (const [engineer, buckets] of Object.entries(engineers ?? {})) {
    for (const bucket of ["blocked", "doing", "next", "done"]) {
      for (const item of buckets[bucket] ?? []) {
        rows.push({ engineer, bucket, ...item });
      }
    }
  }
  return rows;
}

export function standupHistoryColumns() {
  return [
    { key: "date", label: "Date" },
    { key: "bucket", label: "Status", render: (r) => bucketPill(r.bucket) },
    { key: "ticket_id", label: "Ticket" },
    { key: "title", label: "Title" },
    { key: "priority", label: "Priority", render: (r) => priorityPill(r.priority) },
    { key: "blocked_reason", label: "Blocked reason" },
  ];
}

const FLAG_REASON_LABELS = { stale: "Stale", blocked: "Blocked", missing_assignee: "Unassigned" };
const FLAG_REASON_TONE = { stale: "yellow", blocked: "red", missing_assignee: "orange" };

export function ticketWatcherStats(counts) {
  return (counts ?? []).map((c) => ({
    label: FLAG_REASON_LABELS[c.flag_reason] ?? c.flag_reason,
    value: c.ticket_count,
    tone: FLAG_REASON_TONE[c.flag_reason] ?? "gray",
  }));
}

export function bottleneckStats(tickets) {
  const rows = tickets ?? [];
  const dueNow = rows.filter((t) => (t.days_until_sprint_end ?? 99) <= 0).length;
  const thisWeek = rows.filter((t) => {
    const d = t.days_until_sprint_end ?? 99;
    return d > 0 && d <= 2;
  }).length;
  return [
    { label: "At risk", value: rows.length, tone: "purple" },
    { label: "Due now", value: dueNow, tone: "red" },
    { label: "This week", value: thisWeek, tone: "orange" },
  ];
}

export function reviewNudgerStats(reviews) {
  const rows = reviews ?? [];
  const maxWait = rows.reduce((max, r) => Math.max(max, r.hours_waiting ?? 0), 0);
  return [
    { label: "Pending reviews", value: rows.length, tone: "purple" },
    { label: "Longest wait (h)", value: maxWait, tone: "red" },
  ];
}

export function standupStats(rows) {
  const engineers = new Set(rows.map((r) => r.engineer));
  const blocked = rows.filter((r) => r.bucket === "blocked").length;
  return [
    { label: "Engineers", value: engineers.size, tone: "purple" },
    { label: "Blocked items", value: blocked, tone: "red" },
  ];
}

export function flattenStandupDays(days) {
  const rows = [];
  for (const day of days ?? []) {
    for (const bucket of ["blocked", "doing", "next", "done"]) {
      for (const item of day[bucket] ?? []) {
        rows.push({ date: day.date, bucket, ...item });
      }
    }
  }
  return rows;
}
