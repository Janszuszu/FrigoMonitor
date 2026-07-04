const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const WS_URL =
  import.meta.env.VITE_WS_URL ??
  API_BASE_URL.replace(/^http/, "ws").replace(/\/api\/v1\/?$/, "/ws");

async function request(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${path}`);
  }
  return response.json();
}

export function fetchDashboardData() {
  return Promise.all([
    request("/devices"),
    request("/sensors"),
    request("/measurements/latest?limit=100"),
    request("/system/health"),
  ]).then(([devices, sensors, measurements, system]) => ({
    devices,
    sensors,
    measurements,
    system,
  }));
}

export function openLiveSocket({ onMessage, onOpen, onClose, onError }) {
  const socket = new WebSocket(WS_URL);

  socket.addEventListener("open", () => {
    onOpen?.();
  });

  socket.addEventListener("message", (event) => {
    try {
      onMessage?.(JSON.parse(event.data));
    } catch {
      onMessage?.({ event: "unknown", timestamp: new Date().toISOString(), payload: event.data });
    }
  });

  socket.addEventListener("close", () => {
    onClose?.();
  });

  socket.addEventListener("error", () => {
    onError?.();
  });

  return socket;
}
