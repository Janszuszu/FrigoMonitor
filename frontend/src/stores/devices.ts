import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { fetchDevices } from "@/services/api";
import type { Device } from "@/types";

const ONLINE_WINDOW_MS = 5 * 60 * 1000;

export const useDevicesStore = defineStore("devices", () => {
  const items = ref<Device[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const onlineCount = computed(() => {
    const now = Date.now();
    return items.value.filter((device) => {
      if (!device.last_seen) {
        return false;
      }
      return now - new Date(device.last_seen).getTime() < ONLINE_WINDOW_MS;
    }).length;
  });

  async function load(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      items.value = await fetchDevices();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load devices";
    } finally {
      loading.value = false;
    }
  }

  function upsertFromLive(payload: Record<string, unknown> | null): void {
    if (!payload) {
      return;
    }

    const id = Number(payload.id);
    if (!Number.isFinite(id)) {
      return;
    }

    const index = items.value.findIndex((item) => item.id === id);
    const next: Device = {
      id,
      name: String(payload.name || "Unknown device"),
      serial_number: payload.serial_number ? String(payload.serial_number) : null,
      device_id: payload.device_id ? String(payload.device_id) : null,
      location: payload.location ? String(payload.location) : null,
      created_at: payload.created_at ? String(payload.created_at) : null,
      last_seen: payload.last_seen ? String(payload.last_seen) : null,
      firmware: payload.firmware ? String(payload.firmware) : null,
      ip: payload.ip ? String(payload.ip) : null,
      status: payload.status ? String(payload.status) : null,
    };

    if (index >= 0) {
      items.value[index] = {
        ...items.value[index],
        ...next,
      };
      return;
    }

    items.value.unshift(next);
  }

  return {
    items,
    loading,
    error,
    onlineCount,
    load,
    upsertFromLive,
  };
});
