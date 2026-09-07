import { useEffect, useMemo, useState } from "react";

function uniqueValues(rows, key) {
  const values = new Set();
  for (const row of rows) {
    const v = row[key];
    if (v !== null && v !== undefined && v !== "") values.add(v);
  }
  return Array.from(values).sort();
}

function compare(a, b) {
  if (a === null || a === undefined) return -1;
  if (b === null || b === undefined) return 1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b));
}

/**
 * Generic client-side filter/search/sort table. All 4 dashboard panels reuse
 * this with different column/filter configs instead of each hand-rolling
 * table state -- the interaction (filter dropdowns, text search, sortable
 * headers) is identical everywhere.
 */
export default function FilterableTable({
  rows,
  columns,
  filters = [],
  searchKeys = [],
  defaultSort,
  rowKey,
  onFilterChange,
}) {
  const [filterValues, setFilterValues] = useState({});
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState(defaultSort ?? null);

  // Lets a parent (e.g. AgentPanel) react to the same filter/search state the
  // table itself uses, without owning it -- used to keep an AI findings list
  // in sync with whatever the user has filtered the grid to.
  useEffect(() => {
    onFilterChange?.({ filterValues, search });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterValues, search]);

  const filterOptions = useMemo(
    () => filters.map((f) => ({ ...f, options: uniqueValues(rows, f.key) })),
    [rows, filters]
  );

  const visibleRows = useMemo(() => {
    let result = rows;

    for (const f of filters) {
      const selected = filterValues[f.key];
      if (selected && selected !== "All") {
        result = result.filter((row) => String(row[f.key]) === selected);
      }
    }

    if (search.trim() && searchKeys.length > 0) {
      const needle = search.trim().toLowerCase();
      result = result.filter((row) =>
        searchKeys.some((key) => String(row[key] ?? "").toLowerCase().includes(needle))
      );
    }

    if (sort) {
      result = [...result].sort((a, b) => {
        const cmp = compare(a[sort.key], b[sort.key]);
        return sort.direction === "desc" ? -cmp : cmp;
      });
    }

    return result;
  }, [rows, filters, filterValues, search, searchKeys, sort]);

  function toggleSort(key) {
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, direction: "asc" };
      if (prev.direction === "asc") return { key, direction: "desc" };
      return null;
    });
  }

  return (
    <div className="filterable-table">
      <div className="table-controls">
        {filterOptions.map((f) => (
          <select
            key={f.key}
            value={filterValues[f.key] ?? "All"}
            onChange={(e) => setFilterValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
          >
            <option value="All">{f.label}: All</option>
            {f.options.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        ))}
        {searchKeys.length > 0 && (
          <input
            type="text"
            placeholder="Search..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        )}
        <span className="table-count">
          {visibleRows.length} of {rows.length}
        </span>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} onClick={() => toggleSort(col.key)} className="sortable">
                  {col.label}
                  {sort?.key === col.key && (sort.direction === "asc" ? " ▲" : " ▼")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="empty-cell">
                  No rows match the current filters.
                </td>
              </tr>
            )}
            {visibleRows.map((row, i) => (
              <tr key={rowKey ? row[rowKey] : i}>
                {columns.map((col) => (
                  <td key={col.key}>{col.render ? col.render(row) : String(row[col.key] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
