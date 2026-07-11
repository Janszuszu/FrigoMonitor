<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";

import SensorTrendChart from "@/components/SensorTrendChart.vue";
import { fetchMeasurementHistory } from "@/services/api";
import { useAlarmsStore } from "@/stores/alarms";
import { useDevicesStore } from "@/stores/devices";
import { useMeasurementsStore } from "@/stores/measurements";
import { useSensorsStore } from "@/stores/sensors";
import { useSystemStore } from "@/stores/system";

const devicesStore = useDevicesStore();
const sensorsStore = useSensorsStore();
const measurementsStore = useMeasurementsStore();
const alarmsStore = useAlarmsStore();
const systemStore = useSystemStore();

const sensorById = computed(() => new Map(sensorsStore.items.map((sensor) => [sensor.id, sensor])));
const deviceById = computed(() => new Map(devicesStore.items.map((device) => [device.id, device])));
const selectedSensorId = ref<number | null>(null);
const selectedRange = ref<"LIVE" | "1h" | "6h" | "24h" | "72h" | "7d" | "30d" | "CUSTOM">("LIVE");
const customFrom = ref("");
const customTo = ref("");
const trendLoading = ref(false);
const trendError = ref<string | null>(null);
const historyPoints = ref<{ timestamp: string; value: number }[]>([]);

const LIVE_WINDOW_MS = 60 * 60 * 1000;
const LIVE_MAX_POINTS = 500;

const rangeOptions: { key: "LIVE" | "1h" | "6h" | "24h" | "72h" | "7d" | "30d" | "CUSTOM"; label: string }[] = [
  { key: "LIVE", label: "LIVE" },
  { key: "1h", label: "1h" },
  { key: "6h", label: "6h" },
  { key: "24h", label: "24h" },
  { key: "72h", label: "72h" },
  { key: "7d", label: "7d" },
  { key: "30d", label: "30d" },
  { key: "CUSTOM", label: "Custom" },
];

const sensorOptions = computed(() => {
  return sensorsStore.items.map((sensor) => {
    const device = deviceById.value.get(sensor.device_id);
    return {
      id: sensor.id,
      label: `${device?.display_name || device?.name || "Unknown device"} - ${sensor.name || `Sensor ${sensor.id}`}`,
    };
  });
});

watch(
  sensorOptions,
  (options) => {
    if (!options.length) {
      selectedSensorId.value = null;
      return;
    }

    const exists = options.some((option) => option.id === selectedSensorId.value);
    if (!exists) {
      selectedSensorId.value = options[0].id;
    }
  },
  { immediate: true },
);

const selectedSensorLabel = computed(() => {
  return sensorOptions.value.find((option) => option.id === selectedSensorId.value)?.label || "No sensor selected";
});

const isLive = computed(() => selectedRange.value === "LIVE");

const livePoints = computed(() => {
  if (selectedSensorId.value === null) {
    return [];
  }

  const cutoff = Date.now() - LIVE_WINDOW_MS;

  return measurementsStore.items
    .filter((item) => item.sensor_id === selectedSensorId.value)
    .filter((item) => {
      const ts = new Date(item.measured_at).getTime();
      return Number.isFinite(ts) && ts >= cutoff;
    })
    .slice()
    .sort((a, b) => new Date(a.measured_at).getTime() - new Date(b.measured_at).getTime())
    .slice(-LIVE_MAX_POINTS)
    .map((item) => ({
      timestamp: item.measured_at,
      value: item.value,
    }));
});

const trendPoints = computed(() => (isLive.value ? livePoints.value : historyPoints.value));

function localDateTimeToIso(value: string): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toISOString();
}

function buildPresetRange(range: "1h" | "6h" | "24h" | "72h" | "7d" | "30d"): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to);
  if (range === "1h") {
    from.setHours(from.getHours() - 1);
  } else if (range === "6h") {
    from.setHours(from.getHours() - 6);
  } else if (range === "24h") {
    from.setHours(from.getHours() - 24);
  } else if (range === "72h") {
    from.setHours(from.getHours() - 72);
  } else if (range === "7d") {
    from.setDate(from.getDate() - 7);
  } else {
    from.setDate(from.getDate() - 30);
  }
  return { from: from.toISOString(), to: to.toISOString() };
}

async function loadTrendHistory(): Promise<void> {
  if (selectedSensorId.value === null || isLive.value) {
    historyPoints.value = [];
    trendError.value = null;
    return;
  }

  let from: string | null = null;
  let to: string | null = null;

  if (selectedRange.value === "CUSTOM") {
    from = localDateTimeToIso(customFrom.value);
    to = localDateTimeToIso(customTo.value);
    if (!from || !to) {
      historyPoints.value = [];
      trendError.value = "Set a valid custom date/time range.";
      return;
    }
    if (new Date(from).getTime() > new Date(to).getTime()) {
      historyPoints.value = [];
      trendError.value = "Custom range is invalid: FROM must be earlier than TO.";
      return;
    }
  } else {
    const preset = buildPresetRange(selectedRange.value as "1h" | "6h" | "24h" | "72h" | "7d" | "30d");
    from = preset.from;
    to = preset.to;
  }

  trendLoading.value = true;
  trendError.value = null;
  try {
    const result = await fetchMeasurementHistory({
      sensorId: selectedSensorId.value,
      from,
      to,
      limit: 50000,
      targetPoints: 1600,
    });
    historyPoints.value = result.map((item) => ({
      timestamp: item.measured_at,
      value: item.value,
    }));
  } catch (error) {
    historyPoints.value = [];
    trendError.value = error instanceof Error ? error.message : "Failed to load sensor trend history";
  } finally {
    trendLoading.value = false;
  }
}

watch(
  [selectedSensorId, selectedRange, customFrom, customTo],
  () => {
    void loadTrendHistory();
  },
);

// Fullscreen state
const chartContainerRef = ref<HTMLElement | null>(null);
const isFullscreen = ref(false);

function toggleFullscreen(): void {
  if (!chartContainerRef.value) return;

  if (!document.fullscreenElement) {
    void chartContainerRef.value.requestFullscreen();
  } else {
    void document.exitFullscreen();
  }
}

function onFullscreenChange(): void {
  isFullscreen.value = !!document.fullscreenElement;
}

onMounted(async () => {
  try {
    await Promise.all([systemStore.load(), devicesStore.load(), sensorsStore.load(), measurementsStore.load()]);
    await loadTrendHistory();
  } catch (error) {
    console.error("Failed to load dashboard", error);
  }
  document.addEventListener("fullscreenchange", onFullscreenChange);
});

onBeforeUnmount(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
});
</script>

<template>
  <section class="space-y-3">
    <!-- Sensor Trend section - directly at the top -->
    <section class="space-y-2">
      <!-- Header row: Sensor Trend title + sensor selector -->
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h2 class="text-base font-semibold text-fm-text">
          Sensor Trend
        </h2>

        <label class="flex items-center gap-2 text-xs text-fm-muted">
          Sensor:
          <select
            v-model.number="selectedSensorId"
            class="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs text-fm-text"
          >
            <option
              v-for="option in sensorOptions"
              :key="option.id"
              :value="option.id"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
      </div>

      <!-- Selected sensor info -->
      <div class="rounded-lg border border-slate-800 bg-fm-panelSoft/70 px-3 py-2">
        <span class="text-[11px] uppercase tracking-[0.12em] text-fm-muted">
          Selected Sensor: <span class="text-fm-text">{{ selectedSensorLabel }}</span>
        </span>
      </div>

      <!-- Chart -->
      <div
        ref="chartContainerRef"
        class="relative"
        :class="{ 'fm-fullscreen': isFullscreen }"
      >
        <SensorTrendChart
          v-if="trendPoints.length"
          :points="trendPoints"
          :live-mode="isLive"
          :sensor-label="selectedSensorLabel"
          :fullscreen="isFullscreen"
          @toggle-fullscreen="toggleFullscreen"
        />

        <article
          v-else-if="!trendLoading"
          class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4 text-sm text-fm-muted"
        >
          No measurements available yet for the selected sensor.
        </article>

        <article
          v-if="trendLoading"
          class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4 text-sm text-fm-muted"
        >
          Loading trend data...
        </article>

        <article
          v-if="measurementsStore.error || trendError"
          class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4 text-sm text-fm-muted"
        >
          {{ trendError || "Measurements unavailable (REST). Showing live data when available." }}
        </article>
      </div>

      <!-- Time range buttons below the chart -->
      <div class="rounded-lg border border-slate-800 bg-fm-panelSoft/50 px-3 py-2.5">
        <div class="flex flex-wrap items-center gap-1.5">
          <button
            v-for="option in rangeOptions"
            :key="option.key"
            type="button"
            class="rounded-md border px-2.5 py-1 text-[11px] font-semibold transition"
            :class="selectedRange === option.key
              ? 'border-fm-accent bg-fm-accent/20 text-fm-text'
              : 'border-slate-700 bg-slate-900 text-fm-muted hover:border-slate-500 hover:text-fm-text'"
            @click="selectedRange = option.key"
          >
            {{ option.label }}
          </button>
        </div>

        <div
          v-if="selectedRange === 'CUSTOM'"
          class="mt-2 grid gap-2 md:grid-cols-2"
        >
          <label class="text-[11px] text-fm-muted">
            FROM
            <input
              v-model="customFrom"
              type="datetime-local"
              class="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-fm-text"
            >
          </label>
          <label class="text-[11px] text-fm-muted">
            TO
            <input
              v-model="customTo"
              type="datetime-local"
              class="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-fm-text"
            >
          </label>
        </div>
      </div>
    </section>

    <!-- Source and samples info -->
    <div class="grid gap-3 md:grid-cols-2">
      <article class="rounded-lg border border-slate-800 bg-fm-panelSoft px-3 py-2 text-xs text-fm-muted">
        Source: {{ selectedSensorLabel }}
      </article>
      <article class="rounded-lg border border-slate-800 bg-fm-panelSoft px-3 py-2 text-xs text-fm-muted">
        Samples in chart: {{ trendPoints.length }}
      </article>
    </div>
  </section>
</template>

<style scoped>
.fm-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: #05070b;
  padding: 1rem;
  display: flex;
  flex-direction: column;
}
</style>
