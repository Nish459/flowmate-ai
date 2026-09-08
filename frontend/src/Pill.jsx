const TONES = {
  red: "pill-red",
  orange: "pill-orange",
  yellow: "pill-yellow",
  blue: "pill-blue",
  green: "pill-green",
  purple: "pill-purple",
  gray: "pill-gray",
};

export default function Pill({ tone = "gray", children }) {
  if (children === null || children === undefined || children === "") return null;
  return <span className={`pill ${TONES[tone] ?? TONES.gray}`}>{children}</span>;
}

const PRIORITY_TONES = { 1: "red", 2: "orange", 3: "blue", 4: "gray" };

export function priorityPill(priority) {
  if (priority === null || priority === undefined) return null;
  return (
    <Pill tone={PRIORITY_TONES[priority] ?? "gray"}>P{priority}</Pill>
  );
}

const FLAG_REASON_TONES = { blocked: "red", missing_assignee: "orange", stale: "yellow" };

export function flagReasonPill(reason) {
  return <Pill tone={FLAG_REASON_TONES[reason] ?? "gray"}>{reason?.replace("_", " ")}</Pill>;
}

const STATE_TONES = {
  Blocked: "red",
  New: "gray",
  Active: "blue",
  "In Review": "purple",
  "Changes Requested": "orange",
  Resolved: "green",
  Closed: "green",
};

export function statePill(state) {
  return <Pill tone={STATE_TONES[state] ?? "gray"}>{state}</Pill>;
}

const BUCKET_TONES = { blocked: "red", doing: "blue", next: "gray", done: "green" };

export function bucketPill(bucket) {
  return <Pill tone={BUCKET_TONES[bucket] ?? "gray"}>{bucket}</Pill>;
}

export function daysLeftPill(days) {
  if (days === null || days === undefined) return null;
  const tone = days <= 0 ? "red" : days <= 2 ? "orange" : "gray";
  return <Pill tone={tone}>{days}d</Pill>;
}

export function missRiskPill(probability) {
  if (probability === null || probability === undefined) return null;
  const tone = probability >= 75 ? "red" : probability >= 50 ? "orange" : probability >= 25 ? "yellow" : "gray";
  return <Pill tone={tone}>{probability}% miss risk</Pill>;
}
