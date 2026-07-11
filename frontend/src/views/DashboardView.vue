<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";

import DashboardChart from "@/components/dashboard/DashboardChart.vue";
import MainSensorCard from "@/components/dashboard/MainSensorCard.vue";
import SensorSelector from "@/components/dashboard/SensorSelector.vue";
import SummaryCards from "@/components/dashboard/SummaryCards.vue";
import SourceInfo from "@/components/dashboard/SourceInfo.vue";
import { fetchMeasurementHistory } from "@/services/api";
import { useAlarmsStore } from "@/stores/alarms";
import { useDevicesStore } from "@/stores/devices";
import { useMeasurementsStore } from "@/stores/measurements";
import { useSensorsStore } from "@/stores/sensors";
import { useSystemStore } from "@/stores/system";
import { parseApiTimestampMillis } from "@/utils/time";

const devicesStore = useDevicesStore();
const sensorsStore = useSensorsStore();
const measurementsStore = useMeasurementsStore();
const alarmsStore = useAlarmsStore();
const systemStore = useSystemStore();

const sensorById = computed(() => new Map(sensorsStore.items.map((s) => [s.id, s])));
const deviceById = computed(() => new Map(devicesStore.items.map((d) => [d.id, d])));

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
  { key: "1h", label: "1H" },
  { key: "6h", label: "6H" },
  { key: "24h", label: "24H" },
  { key: "72h", label: "72H" },
  { key: "7d", label: "7D" },
  { key: "30d", label: "30D" },
  { key: "CUSTOM", label: "CUSTOM" },
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

// Selected sensor details
const selectedSensor = computed(() => {
  if (selectedSensorId.value === null) return null;
  return sensorById.value.get(selectedSensorId.value) || null;
});

const selectedDevice = computed(() => {
  if (!selectedSensor.value) return null;
  return deviceById.value.get(selectedSensor.value.device_id) || null;
});

const deviceName = computed(() => {
  return selectedDevice.value?.display_name || selectedDevice.value?.name || "—";
});

const sensorName = computed(() => {
  return selectedSensor.value?.name || "—";
});

const currentTemp = computed(() => {
  if (!selectedSensor.value) return null;
  return selectedSensor.value.last_value ?? null;
});

const sensorUnit = computed(() => {
  return selectedSensor.value?.unit || "°C";
});

const isOnline = computed(() => {
  if (!selectedSensor.value) return false;
  const lastMeas = parseApiTimestampMillis(selectedSensor.value.last_measurement);
  if (lastMeas === null) return false;
  return Date.now() - lastMeas < 10 * 60 * 1000;
});

const lastUpdate = computed(() => {
  return selectedSensor.value?.last_measurement || null;
});

// Alarm thresholds - not available on Sensor type directly
// These would come from AlarmSettings if needed in the future
const alarmLow = computed(() => null);
const alarmHigh = computed(() => null);
// Trend (last value change)
const trend = computed(() => {
  if (trendPoints.value.length < 2) return null;
  const last = trendPoints.value[trendPoints.value.length - 1].value;
  const prev = trendPoints.value[trendPoints.value.length - 2].value;
  return last - prev;
});

// Min, Max, Avg from chart data
const chartMin = computed(() => {
  if (!trendPoints.value.length) return null;
  return Math.min(...trendPoints.value.map((p) => p.value));
});

const chartMax = computed(() => {
  if (!trendPoints.value.length) return null;
  return Math.max(...trendPoints.value.map((p) => p.value));
});

const chartAvg = computed(() => {
  if (!trendPoints.value.length) return null;
  const sum = trendPoints.value.reduce((acc, p) => acc + p.value, 0);
  return sum / trendPoints.value.length;
});

const isLive = computed(() => selectedRange.value === "LIVE");

const livePoints = computed(() => {
  if (selectedSensorId.value === null) return [];
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
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function buildPresetRange(range: "1h" | "6h" | "24h" | "72h" | "7d" | "30d"): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to);
  if (range === "1h") from.setHours(from.getHours() - 1);
  else if (range === "6h") from.setHours(from.getHours() - 6);
  else if (range === "24h") from.setHours(from.getHours() - 24);
  else if (range === "72h") from.setHours(from.getHours() - 72);
  else if (range === "7d") from.setDate(from.getDate() - 7);
  else from.setDate(from.getDate() - 30);
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
    await Promise.all([
      systemStore.load(),
      devicesStore.load(),
      sensorsStore.load(),
      measurementsStore.load(),
      alarmsStore.loadActiveAlarms(),
    ]);
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
  <div class="mx-auto max-w-6xl space-y-4">
    <!-- Sensor Selector Row -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-base font-bold uppercase tracking-[0.15em] text-fm-text/90">
        Dashboard
      </h1>
      <div class="flex items-center gap-2">
        <span class="text-[10px] uppercase tracking-[0.12em] text-fm-muted/60">Sensor:</span>
        <SensorSelector v-model="selectedSensorId" />
      </div>
    </div>

    <!-- Main Sensor Card + Chart side by side on desktop -->
    <div class="grid gap-4 lg:grid-cols-5">
      <!-- Main Sensor Card -->
      <div class="lg:col-span-2">
        <MainSensorCard
          :device-name="deviceName"
          :sensor-name="sensorName"
          :temperature="currentTemp"
          :unit="sensorUnit"
          :is-online="isOnline"
          :min="chartMin"
          :max="chartMax"
          :average="chartAvg"
          :last-update="lastUpdate"
          :trend="trend"
        />
      </div>

      <!-- Chart -->
      <div
        ref="chartContainerRef"
        class="lg:col-span-3"
        :class="{ 'fm-fullscreen': isFullscreen }"
      >
        <DashboardChart
          v-if="trendPoints.length"
          :points="trendPoints"
          :live-mode="isLive"
          :sensor-label="sensorName"
          :fullscreen="isFullscreen"
          :alarm-low="alarmLow"
          :alarm-high="alarmHigh"
          @toggle-fullscreen="toggleFullscreen"
        />

        <article
          v-else-if="!trendLoading"
          class="flex min-h-[200px] items-center justify-center rounded-xl border border-slate-700/40 bg-fm-panelSoft/60 p-6 text-sm text-fm-muted"
        >
          <div class="text-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="mx-auto mb-2 h-8 w-8 text-fm-muted/30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            <p>No measurements available yet for the selected sensor.</p>
          </div>
        </article>

        <article
          v-if="trendLoading"
          class="flex min-h-[200px] items-center justify-center rounded-xl border border-slate-700/40 bg-fm-panelSoft/60 p-6 text-sm text-fm-muted"
        >
          <div class="flex items-center gap-2">
            <svg class="h-4 w-4 animate-spin text-fm-accent" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span>Loading trend data...</span>
          </div>
        </article>

        <article
          v-if="trendError"
          class="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-400"
        >
          {{ trendError }}
        </article>
      </div>
    </div>

    <!-- Time range controls -->
    <div class="flex flex-wrap items-center gap-1.5">
      <button
        v-for="option in rangeOptions"
        :key="option.key"
        type="button"
        class="rounded-md border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider transition"
        :class="selectedRange === option.key
          ? 'border-fm-accent/60 bg-fm-accent/15 text-fm-accent'
          : 'border-slate-700/50 bg-slate-900/60 text-fm-muted/70 hover:border-slate-500/50 hover:text-fm-text'"
        @click="selectedRange = option.key"
      >
        {{ option.label }}
      </button>
    </div>

    <!-- Custom range inputs -->
    <div
      v-if="selectedRange === 'CUSTOM'"
      class="grid gap-3 md:grid-cols-2"
    >
      <label class="text-[10px] uppercase tracking-[0.12em] text-fm-muted/60">
        FROM
        <input
          v-model="customFrom"
          type="datetime-local"
          class="mt-1 w-full rounded-lg border border-slate-700/60 bg-slate-900/80 px-3 py-1.5 text-xs text-fm-text outline-none focus:border-fm-accent/60"
        >
      </label>
      <label class="text-[10px] uppercase tracking-[0.12em] text-fm-muted/60">
        TO
        <input
          v-model="customTo"
          type="datetime-local"
          class="mt-1 w-full rounded-lg border border-slate-700/60 bg-slate-900/80 px-3 py-1.5 text-xs text-fm-text outline-none focus:border-fm-accent/60"
        >
      </label>
    </div>

    <!-- Summary Cards -->
    <SummaryCards
      :system-status="systemStore.health?.status || 'unknown'"
      :total-devices="devicesStore.items.length"
      :online-devices="devicesStore.onlineCount"
      :active-alarms="alarmsStore.count"
    />

    <!-- Source Information -->
    <SourceInfo
      :device-name="deviceName"
      :sensor-name="sensorName"
      :sample-count="trendPoints.length"
    />
  </div>
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

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
