import Markdown from "./Markdown";

// Maps a grid filter's key to the tag array field on a finding that should be
// checked against it. Only keys present here are ever applied to findings --
// a table filter with no entry (or "All" selected) never narrows the list.
// Each of the 4 agent tabs uses a different subset of these, matching that
// tab's own grid filters (see the `filters` config passed to FilterableTable
// in App.jsx) -- a finding for a tab just won't carry tags for fields that
// tab doesn't filter on, so those entries are simply never looked up.
const FILTER_TO_TAG_FIELD = {
  team: "teams",
  flag_reason: "flag_reasons",
  work_item_type: "work_item_types",
  state: "states",
  reviewer: "reviewers",
  engineer: "engineers",
  bucket: "buckets",
};

function findingMatches(finding, filterValues, search) {
  for (const [filterKey, selected] of Object.entries(filterValues)) {
    if (!selected || selected === "All") continue;
    const tagField = FILTER_TO_TAG_FIELD[filterKey];
    if (!tagField) continue;
    if (!finding[tagField]?.includes(selected)) return false;
  }

  if (search?.trim()) {
    const needle = search.trim().toLowerCase();
    const tagValues = Object.values(FILTER_TO_TAG_FIELD)
      .flatMap((field) => finding[field] ?? [])
      .join(" ");
    const haystack = `${finding.title} ${finding.body} ${tagValues}`.toLowerCase();
    if (!haystack.includes(needle)) return false;
  }

  return true;
}

export default function FindingsList({ findings, activeFilters }) {
  const { filterValues = {}, search = "" } = activeFilters ?? {};
  const visible = findings.filter((f) => findingMatches(f, filterValues, search));

  if (visible.length === 0) {
    return <p className="panel-meta">No AI findings match the current filter.</p>;
  }

  return (
    <div className="findings-list">
      {visible.map((f, i) => (
        <div key={i} className="finding-card">
          <h3 className="finding-title">{f.title}</h3>
          <Markdown text={f.body} />
        </div>
      ))}
    </div>
  );
}
