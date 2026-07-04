import { ref } from "vue";
import { defineStore } from "pinia";

import {
  fetchSystemHealth,
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
  const backendUrl = ref(getApiBaseUrl());
  const websocketUrl = ref(getStoredWsUrl());
  const theme = ref<ThemeName>((localStorage.getItem(THEME_STORAGE_KEY) as ThemeName) || "dark");

  async function load(): Promise<void> {
    health.value = await fetchSystemHealth();
    network.value = await fetchSystemNetwork();
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

  return {
    health,
    network,
    backendUrl,
    websocketUrl,
    theme,
    load,
    setBackendUrl,
    setWebsocketUrl,
    setTheme,
    applyTheme,
  };
});
