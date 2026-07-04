import { ref } from "vue";
import { defineStore } from "pinia";

import {
  fetchSystem,
  fetchSystemNetwork,
  getApiBaseUrl,
  setApiBaseUrl,
} from "@/services/api";
import { getStoredWsUrl, setStoredWsUrl } from "@/services/websocket";
import type { NetworkSettings, SystemHealth } from "@/types";

type ThemeName = "dark" | "light";

const THEME_STORAGE_KEY = "fm_theme";

export const useSystemStore = defineStore("system", () => {
  const health = ref<SystemHealth | null>(null);
  const network = ref<NetworkSettings | null>(null);
  const error = ref<string | null>(null);
  const backendUrl = ref(getApiBaseUrl());
  const websocketUrl = ref(getStoredWsUrl());
  const theme = ref<ThemeName>((localStorage.getItem(THEME_STORAGE_KEY) as ThemeName) || "dark");

  async function load(): Promise<void> {
    error.value = null;
    try {
      health.value = await fetchSystem();
      network.value = await fetchSystemNetwork();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "System API unavailable";
      if (!health.value) {
        health.value = {
          status: "unavailable",
          name: "FrigoMonitor",
          version: "unknown",
        };
      }
    }
  }

  function setBackendUrl(url: string): void {
    backendUrl.value = url;
    setApiBaseUrl(url);
  }

  function setWebsocketUrl(url: string): void {
    websocketUrl.value = url;
    setStoredWsUrl(url);
  }

  function setTheme(nextTheme: ThemeName): void {
    theme.value = nextTheme;
    localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    applyTheme();
  }

  function applyTheme(): void {
    document.documentElement.dataset.theme = theme.value;
    document.body.classList.toggle("light-theme", theme.value === "light");
  }

  function patchFromLive(payload: Record<string, unknown> | null): void {
    if (!payload) {
      return;
    }
    health.value = {
      status: String(payload.status || health.value?.status || "running"),
      name: String(payload.name || health.value?.name || "FrigoMonitor"),
      version: String(payload.version || health.value?.version || "unknown"),
      app: String(payload.app || health.value?.app || "FrigoMonitor"),
    };
  }

  return {
    health,
    network,
    error,
    backendUrl,
    websocketUrl,
    theme,
    load,
    setBackendUrl,
    setWebsocketUrl,
    setTheme,
    applyTheme,
    patchFromLive,
  };
});
