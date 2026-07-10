import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { fetchActiveAlarms, fetchAlarmHistory, fetchAlarmSettings } from "@/services/api";
import { useDevicesStore } from "@/stores/devices";
import { useSensorsStore } from "@/stores/sensors";
import type { ActiveAlarm, AlarmHistoryItem, AlarmSettings } from "@/types";

export const useAlarmsStore = defineStore("alarms", () => {
  const devicesStore = useDevicesStore();
  const sensorsStore = useSensorsStore();

  const settings = ref<AlarmSettings[]>([]);
  const activeAlarms = ref<ActiveAlarm[]>([]);
  const alarmHistory = ref<AlarmHistoryItem[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const count = computed(() => activeAlarms.value.length);

  async function loadSettings(): Promise<void> {
    try {
      settings.value = await fetchAlarmSettings();
    } catch (err) {
      console.error("Failed to load alarm settings", err);
    }
  }

  async function loadActiveAlarms(): Promise<void> {
    try {
      activeAlarms.value = await fetchActiveAlarms();
    } catch (err) {
      console.error("Failed to load active alarms", err);
    }
  }

  async function loadHistory(sensorId?: number, limit = 100): Promise<void> {
    try {
      alarmHistory.value = await fetchAlarmHistory(sensorId, limit);
    } catch (err) {
      console.error("Failed to load alarm history", err);
    }
  }

  function getDeviceDisplayName(deviceId: number): string {
    const device = devicesStore.items.find((d) => d.id === deviceId);
    return device?.display_name || device?.name || "Unknown";
  }

  function getSensorDisplayName(sensorId: number): string {
    const sensor = sensorsStore.items.find((s) => s.id === sensorId);
    return sensor?.name || "Unknown";
  }

  function activateFromLive(payload: Record<string, unknown> | null, timestamp: string | null): void {
    if (!payload) {
      return;
    }
    const sensorId = Number(payload.sensor_id);
    if (!Number.isFinite(sensorId)) {
      return;
    }
    sensorsStore.patchById(sensorId, {
      alarm_state: String(payload.alarm_state || payload.state || "ALARM"),
      alarm_level: String(payload.level || "warning"),
      last_measurement: timestamp || undefined,
    });
    // Reload active alarms to keep in sync
    loadActiveAlarms();
  }

  function clearFromLive(payload: Record<string, unknown> | null): void {
    if (!payload) {
      return;
    }
    const sensorId = Number(payload.sensor_id);
    if (!Number.isFinite(sensorId)) {
      return;
    }
    sensorsStore.patchById(sensorId, {
      alarm_state: "NORMAL",
      alarm_level: null,
    });
    // Reload active alarms to keep in sync
    loadActiveAlarms();
  }

  return {
    settings,
    activeAlarms,
    alarmHistory,
    loading,
    error,
    count,
    loadSettings,
    loadActiveAlarms,
    loadHistory,
    getDeviceDisplayName,
    getSensorDisplayName,
    activateFromLive,
    clearFromLive,
  };
});
