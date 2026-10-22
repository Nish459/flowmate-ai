const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const ACCESS_CODE_KEY = "flowmate-access-code";

// Endpoints that spend Gemini quota or rewrite the cache need the shared access
// code (X-Access-Code). It's asked for once on the first 401 and remembered in
// this browser; storage can be unavailable, so every access is guarded.
function storedAccessCode() {
  try {
    return localStorage.getItem(ACCESS_CODE_KEY) ?? "";
  } catch {
    return "";
  }
}

function rememberAccessCode(code) {
  try {
    if (code) localStorage.setItem(ACCESS_CODE_KEY, code);
    else localStorage.removeItem(ACCESS_CODE_KEY);
  } catch {
    // Not persisted; the code still works for this request.
  }
}

async function requestJson(path, { method = "GET", gated = false } = {}) {
  const send = (code) =>
    fetch(`${API_BASE_URL}${path}`, { method, headers: code ? { "X-Access-Code": code } : {} });

  let res = await send(gated ? storedAccessCode() : "");
  if (gated && res.status === 401) {
    const code = window.prompt("Enter the FlowMate access code to run this action:")?.trim() ?? "";
    rememberAccessCode("");
    if (code) {
      res = await send(code);
      if (res.ok) rememberAccessCode(code);
    }
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${body ? `: ${body}` : ""}`);
  }
  return res.json();
}

function getJson(path) {
  return requestJson(path);
}

export function getLatestScan() {
  return getJson("/scan/latest");
}

export function getLatestPanels() {
  return getJson("/panels/latest");
}

export function refreshPanels() {
  return requestJson("/panels", { gated: true });
}

export function getEngineers() {
  return getJson("/engineers");
}

export function generatePersonalStandup(engineer, force = false) {
  const qs = force ? "?force=true" : "";
  return requestJson(`/standups/${encodeURIComponent(engineer)}/generate${qs}`, { method: "POST", gated: true });
}

export function getStandupHistory(engineer, start, end) {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const qs = params.toString();
  return getJson(`/standups/${encodeURIComponent(engineer)}${qs ? `?${qs}` : ""}`);
}
