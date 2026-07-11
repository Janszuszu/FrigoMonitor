<script setup lang="ts">
import { onMounted, reactive, ref, computed } from "vue";

import { useAlarmsStore } from "@/stores/alarms";
import { useSystemStore } from "@/stores/system";
import { updateAllAlarmSettings } from "@/services/api";
import type { AlarmSettings } from "@/types";

const systemStore = useSystemStore();
const alarmsStore = useAlarmsStore();

const form = reactive({
  backendUrl: systemStore.backendUrl,
  websocketUrl: systemStore.websocketUrl,
  theme: systemStore.theme,
});

// Track unsaved changes
const dirty = ref(false);
const saving = ref(false);
const saveMessage = ref<string | null>(null);
const saveError = ref<string | null>(null);

// Deep clone of original settings for change detection
const originalSettings = ref<string>("");

function save(): void {
  systemStore.setBackendUrl(form.backendUrl.trim());
  systemStore.setWebsocketUrl(form.websocketUrl.trim());
  systemStore.setTheme(form.theme);
  console.info("Settings saved");
}

function markDirty(): void {
  dirty.value = true;
  saveMessage.value = null;
  saveError.value = null;
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

async function saveAllAlarmSettings(): Promise<void> {
  saving.value = true;
  saveMessage.value = null;
  saveError.value = null;

  try {
    const payload = alarmsStore.settings.map((s) => ({
      sensor_id: s.sensor_id,
      alarm_enabled: s.alarm_enabled,
      alarm_low: s.alarm_low,
      alarm_high: s.alarm_high,
      alarm_activation_delay: s.alarm_activation_delay,
      alarm_no_data_enabled: s.alarm_no_data_enabled,
      alarm_no_data_timeout: s.alarm_no_data_timeout,
    }));

    await updateAllAlarmSettings(payload);

    // Reload settings from backend to verify persistence
    await alarmsStore.loadSettings();

    // Clear dirty state after successful save
    dirty.value = false;
    originalSettings.value = JSON.stringify(alarmsStore.settings);
    saveMessage.value = "Alarm settings saved successfully.";
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to save alarm settings";
    saveError.value = message;
    console.error("Failed to save alarm settings", err);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await alarmsStore.loadSettings();
  originalSettings.value = JSON.stringify(alarmsStore.settings);
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
              @change="setting.alarm_enabled = !setting.alarm_enabled; markDirty()"
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
              @input="setting.alarm_low = ($event.target as HTMLInputElement).value ? Number(($event.target as HTMLInputElement).value) : null; markDirty()"
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
              @input="setting.alarm_high = ($event.target as HTMLInputElement).value ? Number(($event.target as HTMLInputElement).value) : null; markDirty()"
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
              @input="setting.alarm_activation_delay = Number(($event.target as HTMLInputElement).value) * 60; markDirty()"
            >
          </label>

          <!-- No Data Enabled -->
          <label class="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              :checked="setting.alarm_no_data_enabled"
              class="rounded border-slate-700 bg-fm-panel text-fm-accent"
              @change="setting.alarm_no_data_enabled = !setting.alarm_no_data_enabled; markDirty()"
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
              @input="setting.alarm_no_data_timeout = Number(($event.target as HTMLInputElement).value); markDirty()"
            >
          </label>
        </div>
      </div>

      <!-- Save Alarm Settings Button -->
      <div class="flex flex-col items-start gap-3 pt-2">
        <div class="flex items-center gap-3">
          <button
            :disabled="saving"
            class="rounded-lg px-5 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50"
            :class="dirty
              ? 'bg-fm-accent text-slate-900 hover:brightness-110'
              : 'bg-slate-700 text-fm-muted'"
            @click="saveAllAlarmSettings"
          >
            {{ saving ? "Saving..." : "Save Alarm Settings" }}
          </button>
          <span
            v-if="dirty && !saving"
            class="text-xs font-medium text-yellow-400"
          >
            Unsaved changes
          </span>
        </div>
        <p
          v-if="saveMessage"
          class="text-sm font-medium text-green-400"
        >
          {{ saveMessage }}
        </p>
        <p
          v-if="saveError"
          class="text-sm font-medium text-red-400"
        >
          {{ saveError }}
        </p>
      </div>
    </section>
  </section>
</template>
