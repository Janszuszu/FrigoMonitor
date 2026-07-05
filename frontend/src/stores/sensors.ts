import { ref } from "vue";
import { defineStore } from "pinia";

import { fetchSensors } from "@/services/api";
import type { Sensor } from "@/types";

export const useSensorsStore = defineStore("sensors", () => {
  const items = ref<Sensor[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function load(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      items.value = await fetchSensors();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load sensors";
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

    const next: Sensor = {
      id,
      device_id:
        payload.device_id !== undefined
          ? Number(payload.device_id)
          : current?.device_id || 0,
      name:
        payload.name !== undefined
          ? String(payload.name)
          : current?.name || "Unknown sensor",
      sensor_id:
        payload.sensor_id !== undefined
          ? (payload.sensor_id ? String(payload.sensor_id) : null)
          : current?.sensor_id || null,
      sensor_type:
        payload.sensor_type !== undefined
          ? (payload.sensor_type ? String(payload.sensor_type) : null)
          : current?.sensor_type || null,
      address:
        payload.address !== undefined
          ? (payload.address ? String(payload.address) : null)
          : current?.address || null,
      rom:
        payload.rom !== undefined
          ? (payload.rom ? String(payload.rom) : null)
          : current?.rom || null,
      correction:
        payload.correction !== undefined
          ? Number(payload.correction)
          : current?.correction || null,
      alarm_state:
        payload.alarm_state !== undefined
          ? String(payload.alarm_state)
          : current?.alarm_state || "NORMAL",
      alarm_level:
        payload.alarm_level !== undefined
          ? (payload.alarm_level ? String(payload.alarm_level) : null)
          : current?.alarm_level || null,
      last_value:
        payload.last_value !== undefined
          ? Number(payload.last_value)
          : current?.last_value || null,
      last_measurement:
        payload.last_measurement !== undefined
          ? (payload.last_measurement ? String(payload.last_measurement) : null)
          : current?.last_measurement || null,
      unit:
        payload.unit !== undefined
          ? (payload.unit ? String(payload.unit) : null)
          : current?.unit || null,
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

  function patchById(sensorId: number, patch: Partial<Sensor>): void {
    const index = items.value.findIndex((item) => item.id === sensorId);
    if (index < 0) {
      return;
    }
    items.value[index] = {
      ...items.value[index],
      ...patch,
    };
  }

  return {
    items,
    loading,
    error,
    load,
    upsertFromLive,
    patchById,
  };
});
