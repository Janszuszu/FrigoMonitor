<script setup lang="ts">
import { onMounted } from "vue";

import DeviceTable from "@/components/DeviceTable.vue";
import { useDevicesStore } from "@/stores/devices";

const devicesStore = useDevicesStore();

onMounted(async () => {
  try {
    await devicesStore.load();
  } catch (error) {
    console.error("Failed to load devices", error);
  }
});
</script>

<template>
  <section class="space-y-6">
    <header>
      <h2 class="text-2xl font-semibold">
        Devices
      </h2>
      <p class="text-sm text-fm-muted">
        Registered devices from backend API.
      </p>
    </header>

    <DeviceTable :devices="devicesStore.items" />

    <p
      v-if="devicesStore.error"
      class="text-sm text-fm-muted"
    >
      Device API unavailable. Keeping last known data.
    </p>
  </section>
</template>
