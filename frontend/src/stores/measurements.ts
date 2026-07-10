import { computed, onBeforeUnmount, ref } from "vue";
import { defineStore } from "pinia";

import { fetchMeasurements } from "@/services/api";
import { FrigoWebSocket } from "@/services/websocket";
import { useAlarmsStore } from "@/stores/alarms";
import { useDevicesStore } from "@/stores/devices";
import { useSensorsStore } from "@/stores/sensors";
import type { LiveEvent, Measurement } from "@/types";

export const useMeasurementsStore = defineStore("measurements", () => {
  const devicesStore = useDevicesStore();
  const sensorsStore = useSensorsStore();
  const alarmsStore = useAlarmsStore();

  const items = ref<Measurement[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const wsState = ref<"connected" | "connecting" | "disconnected">("disconnected");

  const latest = computed(() => items.value.slice(0, 8));

  const socket = new FrigoWebSocket(handleLiveEvent, (state) => {
    wsState.value = state;
  });

  async function load(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      items.value = await fetchMeasurements(50);
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Failed to load measurements";
    } finally {
      loading.value = false;
    }
  }

  function connect(): void {
    socket.connect();
  }

  function disconnect(): void {
    socket.disconnect();
  }

  function handleLiveEvent(event: LiveEvent): void {
    const eventName = event.event;
    if (!eventName) {
      return;
    }

    if (eventName === "measurement_update") {
      handleMeasurementSaved(event);
      return;
    }

    if (eventName === "device_update") {
      devicesStore.upsertFromLive(event.payload || null);
      return;
    }

    if (eventName === "sensor_update") {
      sensorsStore.upsertFromLive(event.payload || null);
      return;
    }

    if (eventName === "alarm_update") {
      const payload = (event.payload || {}) as Record<string, unknown>;
      const state = String(payload.state || "").toLowerCase();
      if (state.includes("cleared")) {
        alarmsStore.clearFromLive(payload);
      } else {
        alarmsStore.activateFromLive(payload, event.timestamp || null);
      }
      return;
    }

    // Ignore unknown events safely.
  }

  function handleMeasurementSaved(event: LiveEvent): void {
    const payload = (event.payload || {}) as Record<string, unknown>;
    const value = Number(payload.value);
    const sensorId = Number(payload.sensor_id);
    const measuredAt = String(payload.timestamp || event.timestamp || new Date().toISOString());

    if (!Number.isFinite(value) || !Number.isFinite(sensorId)) {
      return;
    }

    const liveMeasurement: Measurement = {
      id: Number(payload.measurement_id || Date.now()),
      sensor_id: sensorId,
      measured_at: measuredAt,
      value,
      unit: null,
      created_at: measuredAt,
    };

    items.value = [liveMeasurement, ...items.value.filter((item) => item.id !== liveMeasurement.id)].slice(0, 500);

    sensorsStore.patchById(sensorId, {
      last_value: value,
      last_measurement: measuredAt,
    });
  }

  onBeforeUnmount(() => {
    socket.disconnect();
  });

  return {
    items,
    latest,
    loading,
    error,
    wsState,
    load,
    connect,
    disconnect,
  };
});
