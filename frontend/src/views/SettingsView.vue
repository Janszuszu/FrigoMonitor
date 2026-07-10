<script setup lang="ts">
import { onMounted, reactive } from "vue";

import { useAlarmsStore } from "@/stores/alarms";
import { useSystemStore } from "@/stores/system";
import { updateAlarmSettings } from "@/services/api";
import type { AlarmSettings } from "@/types";

const systemStore = useSystemStore();
const alarmsStore = useAlarmsStore();

const form = reactive({
  backendUrl: systemStore.backendUrl,
  websocketUrl: systemStore.websocketUrl,
  theme: systemStore.theme,
});

const savingAlarm = reactive<Record<number, boolean>>({});

function save(): void {
  systemStore.setBackendUrl(form.backendUrl.trim());
  systemStore.setWebsocketUrl(form.websocketUrl.trim());
  systemStore.setTheme(form.theme);
  console.info("Settings saved");
}

async function saveAlarmSettings(settings: AlarmSettings): Promise<void> {
  savingAlarm[settings.sensor_id] = true;
  try {
    await updateAlarmSettings(settings.sensor_id, {
      alarm_enabled: settings.alarm_enabled,
      alarm_low: settings.alarm_low,
      alarm_high: settings.alarm_high,
      alarm_activation_delay: settings.alarm_activation_delay,
      alarm_no_data_enabled: settings.alarm_no_data_enabled,
      alarm_no_data_timeout: settings.alarm_no_data_timeout,
    });
    await alarmsStore.loadSettings();
  } catch (err) {
    console.error("Failed to save alarm settings", err);
  } finally {
    savingAlarm[settings.sensor_id] = false;
  }
}

function getDeviceDisplayName(setting: AlarmSettings): string {
  return setting.device_display_name || setting.device_name;
}

function getAlarmStatusLabel(state: string): string {
  switch (state) {
    case "NORMAL":
      return "NORMAL";
    case "PENDING_HIGH":
      return "PENDING HIGH";
    case "PENDING_LOW":
      return "PENDING LOW";
    case "ALARM_HIGH":
      return "ALARM HIGH";
    case "ALARM_LOW":
      return "ALARM LOW";
    case "NO_DATA":
      return "NO DATA";
    default:
      return state;
  }
}

function getAlarmStatusClass(state: string): string {
  if (state === "NORMAL") {
    return "text-green-400";
  }
  if (state.includes("HIGH") || state === "ALARM_HIGH") {
    return "text-fm-danger";
  }
  if (state.includes("LOW") || state === "ALARM_LOW") {
    return "text-fm-warn";
  }
  if (state === "NO_DATA") {
    return "text-purple-400";
  }
  if (state.includes("PENDING")) {
    return "text-yellow-400";
  }
  return "text-fm-muted";
}

onMounted(async () => {
  await alarmsStore.loadSettings();
});
</script>

<template>
  <section class="space-y-6">
    <header>
      <h2 class="text-2xl font-semibold">
        Settings
      </h2>
      <p class="text-sm text-fm-muted">
        Connection and presentation settings.
      </p>
    </header>

    <form
      class="max-w-3xl space-y-4 rounded-xl border border-slate-800 bg-fm-panelSoft p-6"
      @submit.prevent="save"
    >
      <label class="block space-y-2 text-sm">
        <span class="font-medium text-fm-muted">Backend URL</span>
        <input
          v-model="form.backendUrl"
          class="w-full rounded-lg border border-slate-700 bg-fm-panel px-3 py-2 text-fm-text outline-none focus:border-fm-accent"
          placeholder="/api/v1"
        >
      </label>

      <label class="block space-y-2 text-sm">
        <span class="font-medium text-fm-muted">WebSocket URL</span>
        <input
          v-model="form.websocketUrl"
          class="w-full rounded-lg border border-slate-700 bg-fm-panel px-3 py-2 text-fm-text outline-none focus:border-fm-accent"
          placeholder="/ws"
        >
      </label>

      <label class="block space-y-2 text-sm">
        <span class="font-medium text-fm-muted">Theme</span>
        <select
          v-model="form.theme"
          class="w-full rounded-lg border border-slate-700 bg-fm-panel px-3 py-2 text-fm-text outline-none focus:border-fm-accent"
        >
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
      </label>

      <button
        type="submit"
        class="rounded-lg bg-fm-accent px-4 py-2 text-sm font-semibold text-slate-900 transition hover:brightness-110"
      >
        Save settings
      </button>
    </form>

    <!-- Alarm Settings Section -->
    <section class="space-y-4">
      <header>
        <h3 class="text-xl font-semibold">
          Alarm Settings
        </h3>
        <p class="text-sm text-fm-muted">
          Configure per-sensor temperature alarm thresholds and no-data detection.
        </p>
      </header>

      <div
        v-if="alarmsStore.settings.length === 0"
        class="rounded-xl border border-slate-800 bg-fm-panelSoft p-6 text-center text-sm text-fm-muted"
      >
        No sensors available. Add sensors to configure alarm settings.
      </div>

      <div
        v-for="setting in alarmsStore.settings"
        :key="setting.sensor_id"
        class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4"
      >
        <div class="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <span class="text-sm font-medium text-fm-muted">{{ getDeviceDisplayName(setting) }}</span>
            <span class="mx-2 text-fm-muted">-</span>
            <span class="text-sm font-semibold text-fm-text">{{ setting.sensor_name }}</span>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-sm text-fm-muted">
              Current:
              <span class="font-semibold text-fm-text">
                {{ setting.current_temperature !== null ? `${setting.current_temperature.toFixed(1)}°C` : "No data" }}
              </span>
            </span>
            <span
              class="rounded-full px-2 py-0.5 text-xs font-semibold uppercase"
              :class="getAlarmStatusClass(setting.alarm_state)"
            >
              {{ getAlarmStatusLabel(setting.alarm_state) }}
            </span>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <!-- Alarm Enabled -->
          <label class="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              :checked="setting.alarm_enabled"
              class="rounded border-slate-700 bg-fm-panel text-fm-accent"
              @change="setting.alarm_enabled = !setting.alarm_enabled; saveAlarmSettings(setting)"
            >
            <span class="font-medium text-fm-muted">Alarm enabled</span>
          </label>

          <!-- Minimum Temperature -->
          <label class="block space-y-1 text-sm">
            <span class="font-medium text-fm-muted">Minimum temperature (°C)</span>
            <input
              :value="setting.alarm_low"
              type="number"
              step="0.1"
              class="w-full rounded-lg border border-slate-700 bg-fm-panel px-3 py-1.5 text-fm-text outline-none focus:border-fm-accent"
              placeholder="e.g. -25"
              @input="setting.alarm_low = ($event.target as HTMLInputElement).value ? Number(($event.target as HTMLInputElement).value) : null"
              @change="saveAlarmSettings(setting)"
            >
          </label>

          <!-- Maximum Temperature -->
          <label class="block space-y-1 text-sm">
            <span class="font-medium text-fm-muted">Maximum temperature (°C)</span>
            <input
              :value="setting.alarm_high"
              type="number"
              step="0.1"
              class="w-full rounded-lg border border-slate-700 bg-fm-panel px-3 py-1.5 text-fm-text outline-none focus:border-fm-accent"
              placeholder="e.g. -15"
              @input="setting.alarm_high = ($event.target as HTMLInputElement).value ? Number(($event.target as HTMLInputElement).value) : null"
              @change="saveAlarmSettings(setting)"
            >
          </label>

          <!-- Delay -->
          <label class="block space-y-1 text-sm">
            <span class="font-medium text-fm-muted">Delay (minutes)</span>
            <input
              :value="Math.floor(setting.alarm_activation_delay / 60)"
              type="number"
              min="0"
              step="1"
              class="w-full rounded-lg border border-slate-700 bg-fm-panel px-3 py-1.5 text-fm-text outline-none focus:border-fm-accent"
              placeholder="e.g. 10"
              @input="setting.alarm_activation_delay = Number(($event.target as HTMLInputElement).value) * 60"
              @change="saveAlarmSettings(setting)"
            >
          </label>

          <!-- No Data Enabled -->
          <label class="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              :checked="setting.alarm_no_data_enabled"
              class="rounded border-slate-700 bg-fm-panel text-fm-accent"
              @change="setting.alarm_no_data_enabled = !setting.alarm_no_data_enabled; saveAlarmSettings(setting)"
            >
            <span class="font-medium text-fm-muted">No Data alarm enabled</span>
          </label>

          <!-- No Data Timeout -->
          <label class="block space-y-1 text-sm">
            <span class="font-medium text-fm-muted">No Data timeout (minutes)</span>
            <input
              :value="setting.alarm_no_data_timeout"
              type="number"
              min="1"
              step="1"
              class="w-full rounded-lg border border-slate-700 bg-fm-panel px-3 py-1.5 text-fm-text outline-none focus:border-fm-accent"
              placeholder="e.g. 15"
              @input="setting.alarm_no_data_timeout = Number(($event.target as HTMLInputElement).value)"
              @change="saveAlarmSettings(setting)"
            >
          </label>
        </div>

        <div class="mt-2 text-right">
          <span
            v-if="savingAlarm[setting.sensor_id]"
            class="text-xs text-fm-muted"
          >Saving...</span>
        </div>
      </div>
    </section>
  </section>
</template>
