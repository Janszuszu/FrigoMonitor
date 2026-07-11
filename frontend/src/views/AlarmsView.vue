<script setup lang="ts">
import { onMounted, ref } from "vue";

import { useAlarmsStore } from "@/stores/alarms";
import { useDevicesStore } from "@/stores/devices";
import { useSensorsStore } from "@/stores/sensors";

const alarmsStore = useAlarmsStore();
const devicesStore = useDevicesStore();
const sensorsStore = useSensorsStore();

const activeTab = ref<"active" | "history">("active");
const showResetAllConfirm = ref(false);
const resettingAlarms = ref<Set<number>>(new Set());
const resettingAll = ref(false);

function formatTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
}

function getDuration(activatedAt: string | null): string {
  if (!activatedAt) {
    return "-";
  }
  const start = new Date(activatedAt).getTime();
  const now = Date.now();
  const diffMs = now - start;
  const minutes = Math.floor(diffMs / 60000);
  const hours = Math.floor(minutes / 60);
  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }
  return `${minutes} minutes`;
}

function getDeviceName(alarm: { device_name: string; device_display_name: string | null }): string {
  return alarm.device_display_name || alarm.device_name;
}

function getAlarmBadgeClass(alarmType: string): string {
  if (alarmType.includes("HIGH") || alarmType === "ALARM_HIGH") {
    return "border-fm-danger/60 bg-fm-danger/20 text-fm-danger";
  }
  if (alarmType.includes("LOW") || alarmType === "ALARM_LOW") {
    return "border-fm-warn/60 bg-fm-warn/20 text-fm-warn";
  }
  if (alarmType === "NO_DATA") {
    return "border-purple-500/60 bg-purple-500/20 text-purple-400";
  }
  if (alarmType.includes("PENDING")) {
    return "border-yellow-500/60 bg-yellow-500/20 text-yellow-400";
  }
  return "border-slate-700 bg-slate-800/70 text-fm-muted";
}

function getAlarmTypeLabel(alarmType: string): string {
  switch (alarmType) {
    case "ALARM_HIGH":
      return "HIGH TEMPERATURE";
    case "ALARM_LOW":
      return "LOW TEMPERATURE";
    case "PENDING_HIGH":
      return "PENDING HIGH";
    case "PENDING_LOW":
      return "PENDING LOW";
    case "NO_DATA":
      return "NO DATA";
    default:
      return alarmType;
  }
}

async function handleResetAlarm(alarmId: number): Promise<void> {
  resettingAlarms.value.add(alarmId);
  try {
    await alarmsStore.resetAlarm(alarmId);
  } finally {
    resettingAlarms.value.delete(alarmId);
  }
}

async function handleResetAll(): Promise<void> {
  showResetAllConfirm.value = false;
  resettingAll.value = true;
  try {
    await alarmsStore.resetAllAlarms();
  } finally {
    resettingAll.value = false;
  }
}

onMounted(async () => {
  try {
    await Promise.all([devicesStore.load(), sensorsStore.load()]);
    await Promise.all([alarmsStore.loadActiveAlarms(), alarmsStore.loadHistory()]);
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
        Active alarms and alarm history.
      </p>
    </header>

    <!-- Tabs -->
    <div class="flex gap-2 border-b border-slate-800 pb-2">
      <button
        class="rounded-lg px-4 py-2 text-sm font-medium transition"
        :class="activeTab === 'active' ? 'bg-fm-accent text-slate-900' : 'text-fm-muted hover:text-fm-text'"
        @click="activeTab = 'active'"
      >
        Active Alarms
        <span
          v-if="alarmsStore.count > 0"
          class="ml-2 rounded-full bg-fm-danger/20 px-2 py-0.5 text-xs text-fm-danger"
        >{{ alarmsStore.count }}</span>
      </button>
      <button
        class="rounded-lg px-4 py-2 text-sm font-medium transition"
        :class="activeTab === 'history' ? 'bg-fm-accent text-slate-900' : 'text-fm-muted hover:text-fm-text'"
        @click="activeTab = 'history'"
      >
        History
      </button>
    </div>

    <!-- Active Alarms -->
    <div v-if="activeTab === 'active'">
      <!-- RESET ALL button -->
      <div
        v-if="alarmsStore.activeAlarms.length > 0"
        class="mb-3 flex items-center justify-end"
      >
        <button
          class="rounded-lg border border-fm-warn/50 bg-fm-warn/10 px-4 py-2 text-sm font-medium text-fm-warn transition hover:bg-fm-warn/20 disabled:opacity-50"
          :disabled="resettingAll"
          @click="showResetAllConfirm = true"
        >
          <span v-if="resettingAll">Resetting...</span>
          <span v-else>RESET ALL ({{ alarmsStore.count }})</span>
        </button>
      </div>

      <!-- Reset All Confirmation Dialog -->
      <div
        v-if="showResetAllConfirm"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
        @click.self="showResetAllConfirm = false"
      >
        <div class="mx-4 w-full max-w-md rounded-xl border border-slate-700 bg-fm-panel p-6 shadow-2xl">
          <h3 class="text-lg font-semibold text-fm-text">
            Reset All Alarms
          </h3>
          <p class="mt-2 text-sm text-fm-muted">
            Are you sure you want to reset all {{ alarmsStore.count }} active alarms?
          </p>
          <p class="mt-1 text-xs text-fm-muted">
            Alarm thresholds and configuration will be preserved. If alarm conditions are still active, new alarms will be created on the next measurement.
          </p>
          <div class="mt-4 flex justify-end gap-3">
            <button
              class="rounded-lg border border-slate-700 px-4 py-2 text-sm text-fm-muted transition hover:bg-slate-800"
              @click="showResetAllConfirm = false"
            >
              Cancel
            </button>
            <button
              class="rounded-lg bg-fm-warn px-4 py-2 text-sm font-medium text-slate-900 transition hover:bg-fm-warn/90"
              @click="handleResetAll"
            >
              Reset All
            </button>
          </div>
        </div>
      </div>

      <div class="overflow-x-auto rounded-xl border border-slate-800 bg-fm-panelSoft">
        <table class="min-w-full text-left text-sm">
          <thead class="border-b border-slate-800 text-xs uppercase tracking-wide text-fm-muted">
            <tr>
              <th class="px-4 py-3">
                Device
              </th>
              <th class="px-4 py-3">
                Sensor
              </th>
              <th class="min-w-[140px] px-4 py-3">
                <span class="whitespace-nowrap">Alarm Type</span>
              </th>
              <th class="px-4 py-3">
                Current Temperature
              </th>
              <th class="px-4 py-3">
                Threshold
              </th>
              <th class="px-4 py-3">
                Active Since
              </th>
              <th class="px-4 py-3">
                Duration
              </th>
              <th class="px-4 py-3">
                <span class="whitespace-nowrap">Status</span>
              </th>
              <th class="px-4 py-3">
                <span class="whitespace-nowrap">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="alarm in alarmsStore.activeAlarms"
              :key="alarm.id"
              class="border-b border-slate-900/70 last:border-b-0"
            >
              <td class="px-4 py-3 text-fm-text">
                {{ getDeviceName(alarm) }}
              </td>
              <td class="px-4 py-3 text-fm-text">
                {{ alarm.sensor_name }}
              </td>
              <td class="px-4 py-3">
                <span
                  class="inline-block whitespace-nowrap rounded-full border px-2 py-1 text-xs font-semibold uppercase"
                  :class="getAlarmBadgeClass(alarm.alarm_type)"
                >
                  {{ getAlarmTypeLabel(alarm.alarm_type) }}
                </span>
              </td>
              <td class="px-4 py-3 text-fm-text">
                {{ alarm.temperature !== null ? `${alarm.temperature.toFixed(1)}°C` : "-" }}
              </td>
              <td class="px-4 py-3 text-fm-muted">
                {{ alarm.threshold !== null ? `${alarm.threshold.toFixed(1)}°C` : "-" }}
              </td>
              <td class="px-4 py-3 text-fm-muted">
                {{ formatTime(alarm.activated_at || alarm.pending_start) }}
              </td>
              <td class="px-4 py-3 text-fm-muted">
                {{ getDuration(alarm.activated_at) }}
              </td>
              <td class="px-4 py-3">
                <span
                  class="inline-block whitespace-nowrap rounded-full border px-2 py-1 text-xs font-semibold uppercase"
                  :class="getAlarmBadgeClass(alarm.state)"
                >
                  {{ alarm.state === "NO_DATA" ? "NO DATA" : alarm.state.includes("PENDING") ? "PENDING" : "ACTIVE" }}
                </span>
              </td>
              <td class="px-4 py-3">
                <button
                  class="rounded-lg border border-fm-warn/50 bg-fm-warn/10 px-3 py-1 text-xs font-medium text-fm-warn transition hover:bg-fm-warn/20 disabled:opacity-50"
                  :disabled="resettingAlarms.has(alarm.id)"
                  @click="handleResetAlarm(alarm.id)"
                >
                  <span v-if="resettingAlarms.has(alarm.id)">...</span>
                  <span v-else>RESET</span>
                </button>
              </td>
            </tr>
            <tr v-if="alarmsStore.activeAlarms.length === 0">
              <td
                colspan="9"
                class="px-4 py-6 text-center text-fm-muted"
              >
                No active alarms
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Alarm History -->
    <div v-if="activeTab === 'history'">
      <div class="overflow-x-auto rounded-xl border border-slate-800 bg-fm-panelSoft">
        <table class="min-w-full text-left text-sm">
          <thead class="border-b border-slate-800 text-xs uppercase tracking-wide text-fm-muted">
            <tr>
              <th class="px-4 py-3">
                Device
              </th>
              <th class="px-4 py-3">
                Sensor
              </th>
              <th class="min-w-[140px] px-4 py-3">
                <span class="whitespace-nowrap">Alarm Type</span>
              </th>
              <th class="px-4 py-3">
                Temperature
              </th>
              <th class="px-4 py-3">
                Threshold
              </th>
              <th class="px-4 py-3">
                Activated
              </th>
              <th class="px-4 py-3">
                Cleared
              </th>
              <th class="px-4 py-3">
                <span class="whitespace-nowrap">Status</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="event in alarmsStore.alarmHistory"
              :key="event.id"
              class="border-b border-slate-900/70 last:border-b-0"
            >
              <td class="px-4 py-3 text-fm-text">
                {{ getDeviceName(event) }}
              </td>
              <td class="px-4 py-3 text-fm-text">
                {{ event.sensor_name }}
              </td>
              <td class="px-4 py-3">
                <span
                  class="inline-block whitespace-nowrap rounded-full border px-2 py-1 text-xs font-semibold uppercase"
                  :class="getAlarmBadgeClass(event.alarm_type)"
                >
                  {{ getAlarmTypeLabel(event.alarm_type) }}
                </span>
              </td>
              <td class="px-4 py-3 text-fm-text">
                {{ event.temperature !== null ? `${event.temperature.toFixed(1)}°C` : "-" }}
              </td>
              <td class="px-4 py-3 text-fm-muted">
                {{ event.threshold !== null ? `${event.threshold.toFixed(1)}°C` : "-" }}
              </td>
              <td class="px-4 py-3 text-fm-muted">
                {{ formatTime(event.activated_at || event.pending_start) }}
              </td>
              <td class="px-4 py-3 text-fm-muted">
                {{ formatTime(event.cleared_at) }}
              </td>
              <td class="px-4 py-3">
                <span
                  class="inline-block whitespace-nowrap rounded-full border px-2 py-1 text-xs font-semibold uppercase"
                  :class="event.state === 'CLEARED' ? 'border-green-500/60 bg-green-500/20 text-green-400' : getAlarmBadgeClass(event.state)"
                >
                  {{ event.state === "CLEARED" ? "RESOLVED" : event.state }}
                </span>
              </td>
            </tr>
            <tr v-if="alarmsStore.alarmHistory.length === 0">
              <td
                colspan="8"
                class="px-4 py-6 text-center text-fm-muted"
              >
                No alarm history
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <p
      v-if="sensorsStore.error"
      class="text-sm text-fm-muted"
    >
      Alarm source API unavailable. Live updates will appear when WebSocket events arrive.
    </p>
  </section>
</template>
