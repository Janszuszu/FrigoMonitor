<script setup lang="ts">
import { computed, onMounted } from "vue";

import SensorTable from "@/components/SensorTable.vue";
import { useDevicesStore } from "@/stores/devices";
import { useSensorsStore } from "@/stores/sensors";

const devicesStore = useDevicesStore();
const sensorsStore = useSensorsStore();

const rows = computed(() => {
  const deviceMap = new Map(devicesStore.items.map((device) => [device.id, device.name]));
  return sensorsStore.items.map((sensor) => ({
    ...sensor,
    deviceName: deviceMap.get(sensor.device_id) || "Unknown",
  }));
});

onMounted(async () => {
  try {
    await Promise.all([devicesStore.load(), sensorsStore.load()]);
  } catch (error) {
    console.error("Failed to load sensors", error);
  }
});
</script>

<template>
  <section class="space-y-6">
    <header>
      <h2 class="text-2xl font-semibold">
        Sensors
      </h2>
      <p class="text-sm text-fm-muted">
        Current sensor state with latest temperatures.
      </p>
    </header>

    <SensorTable :sensors="rows" />
  </section>
</template>
