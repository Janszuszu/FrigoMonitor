import { computed, onBeforeUnmount, ref } from "vue";
import { defineStore } from "pinia";

import { fetchMeasurements } from "@/services/api";
import { FrigoWebSocket } from "@/services/websocket";
import type { LiveEvent, Measurement } from "@/types";

export const useMeasurementsStore = defineStore("measurements", () => {
  const items = ref<Measurement[]>([]);
  const loading = ref(false);
  const wsState = ref<"connected" | "connecting" | "disconnected">("disconnected");

  const latest = computed(() => items.value.slice(0, 8));

  const socket = new FrigoWebSocket(handleLiveEvent, (state) => {
    wsState.value = state;
  });

  async function load(): Promise<void> {
    loading.value = true;
    try {
      items.value = await fetchMeasurements(100);
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
    if (event.event !== "measurement.saved") {
      return;
    }

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

    items.value = [liveMeasurement, ...items.value.filter((item) => item.id !== liveMeasurement.id)].slice(0, 100);
  }

  onBeforeUnmount(() => {
    socket.disconnect();
  });

  return {
    items,
    latest,
    loading,
    wsState,
    load,
    connect,
    disconnect,
  };
});
