const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      ...options.headers,
    },
  });
  if (!response.ok) {
    let message = `Error HTTP ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // El servidor puede responder sin JSON durante un cierre abrupto.
    }
    throw new Error(message);
  }
  return response.json();
}

export function getHealth() {
  return request("/api/health");
}

export function getState() {
  return request("/api/state");
}

export function getPlays(limit = 10) {
  return request(`/api/plays?limit=${limit}`);
}

export function resetPlay() {
  return request("/api/reset", { method: "POST" });
}

export function getCalibrationStatus() {
  return request("/api/admin/calibration/status");
}

export function startCalibration() {
  return request("/api/admin/calibration/start", { method: "POST" });
}

export function resultSnapshotUrl(playId) {
  return `${API_BASE}/api/result-snapshot.jpg?play_id=${playId}`;
}

export function liveSnapshotUrl() {
  return `${API_BASE}/api/snapshot.jpg?t=${Date.now()}`;
}

export function websocketUrl() {
  const configured = import.meta.env.VITE_WS_URL;
  return configured || `${API_BASE.replace(/^http/, "ws")}/ws`;
}
