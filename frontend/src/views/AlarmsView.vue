<script setup lang="ts">
import { onMounted } from "vue";

import AlarmBadge from "@/components/AlarmBadge.vue";
import { useAlarmsStore } from "@/stores/alarms";
import { useDevicesStore } from "@/stores/devices";
import { useSensorsStore } from "@/stores/sensors";

const alarmsStore = useAlarmsStore();
const devicesStore = useDevicesStore();
const sensorsStore = useSensorsStore();

function formatTime(value: string): string {
  if (!value) {
    return "No data";
  }
  return new Date(value).toLocaleString();
}

onMounted(async () => {
  try {
    await Promise.all([devicesStore.load(), sensorsStore.load()]);
  } catch (error) {
    console.error("Failed to load alarms", error);
  }
});
</script>

<template>
  <section class="space-y-6">
    <header>
      <h2 class="text-2xl font-semibold">
        Alarms
      </h2>
      <p class="text-sm text-fm-muted">
        Alarm states derived from sensors.
      </p>
    </header>

    <div class="overflow-x-auto rounded-xl border border-slate-800 bg-fm-panelSoft">
      <table class="min-w-full text-left text-sm">
        <thead class="border-b border-slate-800 text-xs uppercase tracking-wide text-fm-muted">
          <tr>
            <th class="px-4 py-3">
              Severity
            </th>
            <th class="px-4 py-3">
              Device
            </th>
            <th class="px-4 py-3">
              Sensor
            </th>
            <th class="px-4 py-3">
              Message
            </th>
            <th class="px-4 py-3">
              Timestamp
            </th>
            <th class="px-4 py-3">
              Acknowledged
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="alarm in alarmsStore.items"
            :key="alarm.id"
            class="border-b border-slate-900/70 last:border-b-0"
          >
            <td class="px-4 py-3">
              <AlarmBadge :severity="alarm.severity" />
            </td>
            <td class="px-4 py-3 text-fm-text">
              {{ alarm.device }}
            </td>
            <td class="px-4 py-3 text-fm-text">
              {{ alarm.sensor }}
            </td>
            <td class="px-4 py-3 text-fm-muted">
              {{ alarm.message }}
            </td>
            <td class="px-4 py-3 text-fm-muted">
              {{ formatTime(alarm.timestamp) }}
            </td>
            <td class="px-4 py-3 text-fm-muted">
              {{ alarm.acknowledged ? "Yes" : "No" }}
            </td>
          </tr>
          <tr v-if="alarmsStore.items.length === 0">
            <td
              colspan="6"
              class="px-4 py-6 text-center text-fm-muted"
            >
              No active alarms
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p
      v-if="sensorsStore.error"
      class="text-sm text-fm-muted"
    >
      Alarm source API unavailable. Live updates will appear when WebSocket events arrive.
    </p>
  </section>
</template>
