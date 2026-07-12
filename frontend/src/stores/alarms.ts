import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { fetchActiveAlarms, fetchAlarmHistory, fetchAlarmSettings, resetAlarm as apiResetAlarm, resetAllAlarms as apiResetAllAlarms } from "@/services/api";

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
    const sensorId = payload.sensor_id != null ? Number(payload.sensor_id) : null;
    if (sensorId != null && Number.isFinite(sensorId)) {
      sensorsStore.patchById(sensorId, {
        alarm_state: String(payload.alarm_state || payload.state || "ALARM"),
        alarm_level: String(payload.level || "warning"),
        last_measurement: timestamp || undefined,
      });
    }
    // Reload active alarms to keep in sync
    loadActiveAlarms();
  }

  function clearFromLive(payload: Record<string, unknown> | null): void {
    if (!payload) {
      return;
    }
    const sensorId = payload.sensor_id != null ? Number(payload.sensor_id) : null;
    if (sensorId != null && Number.isFinite(sensorId)) {
      sensorsStore.patchById(sensorId, {
        alarm_state: "NORMAL",
        alarm_level: null,
      });
    }
    // Reload active alarms to keep in sync
    loadActiveAlarms();
  }

  async function resetAlarm(alarmId: number): Promise<boolean> {
    try {
      await apiResetAlarm(alarmId);
      // Reload active alarms and history to reflect the change
      await Promise.all([loadActiveAlarms(), loadHistory()]);
      return true;
    } catch (err) {
      console.error("Failed to reset alarm", err);
      error.value = "Failed to reset alarm";
      return false;
    }
  }

  async function resetAllAlarmsAction(): Promise<number> {
    try {
      const result = await apiResetAllAlarms();
      // Reload active alarms and history to reflect the change
      await Promise.all([loadActiveAlarms(), loadHistory()]);
      return result.count;
    } catch (err) {
      console.error("Failed to reset all alarms", err);
      error.value = "Failed to reset all alarms";
      return 0;
    }
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
    resetAlarm,
    resetAllAlarms: resetAllAlarmsAction,
  };

});
