import { computed } from "vue";
import { defineStore } from "pinia";

import { useDevicesStore } from "@/stores/devices";
import { useSensorsStore } from "@/stores/sensors";
import type { AlarmRow } from "@/types";

export const useAlarmsStore = defineStore("alarms", () => {
  const devicesStore = useDevicesStore();
  const sensorsStore = useSensorsStore();

  const items = computed<AlarmRow[]>(() => {
    const deviceMap = new Map(devicesStore.items.map((device) => [device.id, device.name]));

    return sensorsStore.items
      .filter((sensor) => sensor.alarm_state && sensor.alarm_state !== "NORMAL")
      .map((sensor) => ({
        id: `alarm-${sensor.id}`,
        severity: sensor.alarm_level || "warning",
        device: deviceMap.get(sensor.device_id) || "Unknown",
        sensor: sensor.name,
        message: `State: ${sensor.alarm_state}`,
        timestamp: sensor.last_measurement || "",
        acknowledged: false,
      }));
  });

  const count = computed(() => items.value.length);

  return {
    items,
    count,
  };
});
