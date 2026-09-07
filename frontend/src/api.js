const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function getJson(path) {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${body ? `: ${body}` : ""}`);
  }
  return res.json();
}

async function postJson(path) {
  const res = await fetch(`${API_BASE_URL}${path}`, { method: "POST" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${body ? `: ${body}` : ""}`);
  }
  return res.json();
}

export function getLatestScan() {
  return getJson("/scan/latest");
}

export function getLatestPanels() {
  return getJson("/panels/latest");
}

export function refreshPanels() {
  return getJson("/panels");
}

export function getEngineers() {
  return getJson("/engineers");
}

export function generatePersonalStandup(engineer, force = false) {
  const qs = force ? "?force=true" : "";
  return postJson(`/standups/${encodeURIComponent(engineer)}/generate${qs}`);
}

export function getStandupHistory(engineer, start, end) {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const qs = params.toString();
  return getJson(`/standups/${encodeURIComponent(engineer)}${qs ? `?${qs}` : ""}`);
}
