import type { LiveEvent } from "@/types";

const WS_STORAGE_KEY = "fm_ws_url";
const DEFAULT_WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

export type MessageHandler = (event: LiveEvent) => void;
export type StateHandler = (state: "connected" | "connecting" | "disconnected") => void;

export class FrigoWebSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private messageHandler: MessageHandler;
  private stateHandler: StateHandler;
  private reconnectDelayMs = 2000;

  constructor(messageHandler: MessageHandler, stateHandler: StateHandler) {
    this.messageHandler = messageHandler;
    this.stateHandler = stateHandler;
  }

  public connect(url?: string): void {
    const wsUrl = url || localStorage.getItem(WS_STORAGE_KEY) || DEFAULT_WS_URL;
    localStorage.setItem(WS_STORAGE_KEY, wsUrl);

    this.stateHandler("connecting");
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.stateHandler("connected");
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        this.messageHandler(JSON.parse(event.data) as LiveEvent);
      } catch (_error) {
        this.messageHandler({
          event: "raw",
          timestamp: new Date().toISOString(),
          payload: { raw: event.data },
        });
      }
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      this.stateHandler("disconnected");
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.stateHandler("disconnected");
    };
  }

  public disconnect(): void {
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.stopHeartbeat();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.stateHandler("disconnected");
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelayMs);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ event: "ping", timestamp: new Date().toISOString() }));
      }
    }, 15000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
}

export function getStoredWsUrl(): string {
  return localStorage.getItem(WS_STORAGE_KEY) || DEFAULT_WS_URL;
}

export function setStoredWsUrl(url: string): void {
  localStorage.setItem(WS_STORAGE_KEY, url);
}
