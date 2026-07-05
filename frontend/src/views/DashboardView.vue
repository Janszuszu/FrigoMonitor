<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import SensorTrendChart from "@/components/SensorTrendChart.vue";
import StatusCard from "@/components/StatusCard.vue";
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

const sensorOptions = computed(() => {
  const ids = new Set<number>();
  for (const item of measurementsStore.items) {
    ids.add(item.sensor_id);
  }

  return Array.from(ids).map((sensorId) => {
    const sensor = sensorById.value.get(sensorId);
    const device = sensor ? deviceById.value.get(sensor.device_id) : null;
    return {
      id: sensorId,
      label: `${device?.name || "Unknown device"} - ${sensor?.name || `Sensor ${sensorId}`}`,
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

const trendPoints = computed(() => {
  if (selectedSensorId.value === null) {
    return [];
  }

  return measurementsStore.items
    .filter((item) => item.sensor_id === selectedSensorId.value)
    .slice(0, 30)
    .reverse()
    .map((item) => ({
      timestamp: item.measured_at,
      value: item.value,
    }));
});

onMounted(async () => {
  try {
    await Promise.all([systemStore.load(), devicesStore.load(), sensorsStore.load(), measurementsStore.load()]);
  } catch (error) {
    console.error("Failed to load dashboard", error);
  }
});
</script>

<template>
  <section class="space-y-6">
    <header>
      <h2 class="text-2xl font-semibold">
        Dashboard
      </h2>
      <p class="text-sm text-fm-muted">
        Overview of platform state and latest temperatures.
      </p>
    </header>

    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatusCard
        label="System Status"
        :value="systemStore.health?.status || 'N/A'"
      />
      <StatusCard
        label="Backend Version"
        :value="systemStore.health?.version || 'N/A'"
      />
      <StatusCard
        label="Devices"
        :value="devicesStore.items.length"
      />
      <StatusCard
        label="Online Devices"
        :value="devicesStore.onlineCount"
      />
      <StatusCard
        label="Alarms"
        :value="alarmsStore.count"
      />
      <StatusCard
        label="Latest Measurements"
        :value="measurementsStore.latest.length"
      />
    </div>

    <section class="space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h3 class="text-lg font-semibold text-fm-text">
          Sensor Trend
        </h3>

        <label class="flex items-center gap-2 text-sm text-fm-muted">
          Sensor:
          <select
            v-model.number="selectedSensorId"
            class="rounded-md border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-fm-text"
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

      <SensorTrendChart
        v-if="trendPoints.length"
        :points="trendPoints"
      />

      <article
        v-else
        class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4 text-sm text-fm-muted"
      >
        No measurements available yet for the selected sensor.
      </article>

      <article
        v-if="measurementsStore.error"
        class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4 text-sm text-fm-muted"
      >
        Measurements unavailable (REST). Showing live data when available.
      </article>
    </section>

    <div class="grid gap-4 lg:grid-cols-2">
      <article class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4 text-sm text-fm-muted">
        Source: {{ sensorOptions.find((option) => option.id === selectedSensorId)?.label || "No sensor selected" }}
      </article>
      <article class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4 text-sm text-fm-muted">
        Samples in chart: {{ trendPoints.length }}
      </article>
    </div>
  </section>
</template>
