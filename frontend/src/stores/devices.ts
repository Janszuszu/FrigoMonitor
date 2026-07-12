import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { fetchDevices, updateDeviceName } from "@/services/api";
import type { Device } from "@/types";

export const useDevicesStore = defineStore("devices", () => {
  const items = ref<Device[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const onlineCount = computed(() => {
    return items.value.filter((device) => device.online === true).length;
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
    const current = index >= 0 ? items.value[index] : null;

    const next: Device = {
      id,
      name:
        payload.name !== undefined
          ? String(payload.name)
          : current?.name || "Unknown device",
      display_name:
        payload.display_name !== undefined
          ? (payload.display_name ? String(payload.display_name) : null)
          : current?.display_name || null,
      serial_number:
        payload.serial_number !== undefined
          ? (payload.serial_number ? String(payload.serial_number) : null)
          : current?.serial_number || null,
      device_id:
        payload.device_id !== undefined
          ? (payload.device_id ? String(payload.device_id) : null)
          : current?.device_id || null,
      location:
        payload.location !== undefined
          ? (payload.location ? String(payload.location) : null)
          : current?.location || null,
      created_at:
        payload.created_at !== undefined
          ? (payload.created_at ? String(payload.created_at) : null)
          : current?.created_at || null,
      last_seen:
        payload.last_seen !== undefined
          ? (payload.last_seen ? String(payload.last_seen) : null)
          : current?.last_seen || null,
      firmware:
        payload.firmware !== undefined
          ? (payload.firmware ? String(payload.firmware) : null)
          : current?.firmware || null,
      ip:
        payload.ip !== undefined
          ? (payload.ip ? String(payload.ip) : null)
          : current?.ip || null,
      online:
        payload.online !== undefined
          ? Boolean(payload.online)
          : current?.online ?? undefined,
      status:
        payload.status !== undefined
          ? (payload.status ? String(payload.status) : null)
          : current?.status || null,
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

  async function updateName(deviceId: number, displayName: string): Promise<void> {
    const updated = await updateDeviceName(deviceId, displayName);
    const index = items.value.findIndex((item) => item.id === deviceId);
    if (index >= 0) {
      items.value[index] = {
        ...items.value[index],
        display_name: updated.display_name,
      };
    }
  }

  return {
    items,
    loading,
    error,
    onlineCount,
    load,
    upsertFromLive,
    updateName,
  };
});
