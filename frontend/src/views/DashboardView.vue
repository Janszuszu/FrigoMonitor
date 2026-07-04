<script setup lang="ts">
import { computed, onMounted } from "vue";

import StatusCard from "@/components/StatusCard.vue";
import TemperatureCard from "@/components/TemperatureCard.vue";
import { useAlarmsStore } from "@/stores/alarms";
import { useDevicesStore } from "@/stores/devices";
import { useMeasurementsStore } from "@/stores/measurements";
import { useSensorsStore } from "@/stores/sensors";

const devicesStore = useDevicesStore();
const sensorsStore = useSensorsStore();
const measurementsStore = useMeasurementsStore();
const alarmsStore = useAlarmsStore();

const sensorById = computed(() => new Map(sensorsStore.items.map((sensor) => [sensor.id, sensor])));
const deviceById = computed(() => new Map(devicesStore.items.map((device) => [device.id, device])));

const latestCards = computed(() =>
  measurementsStore.latest.map((measurement) => {
    const sensor = sensorById.value.get(measurement.sensor_id);
    const device = sensor ? deviceById.value.get(sensor.device_id) : null;

    return {
      id: measurement.id,
      sensor: sensor?.name || "Unknown sensor",
      device: device?.name || "Unknown device",
      value: measurement.value,
      timestamp: measurement.measured_at,
    };
  }),
);

onMounted(async () => {
  try {
    await Promise.all([devicesStore.load(), sensorsStore.load(), measurementsStore.load()]);
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

    <div class="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
      <TemperatureCard
        v-for="item in latestCards"
        :key="item.id"
        :sensor="item.sensor"
        :device="item.device"
        :value="item.value"
        :timestamp="item.timestamp"
      />
    </div>
  </section>
</template>
