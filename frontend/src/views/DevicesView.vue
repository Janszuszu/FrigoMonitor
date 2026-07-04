<script setup lang="ts">
import { computed, onMounted } from "vue";

import DeviceTable from "@/components/DeviceTable.vue";
import { useDevicesStore } from "@/stores/devices";

const devicesStore = useDevicesStore();

const onlineIds = computed(() => {
  const now = Date.now();
  const set = new Set<number>();
  for (const item of devicesStore.items) {
    if (!item.last_seen) {
      continue;
    }
    if (now - new Date(item.last_seen).getTime() < 5 * 60 * 1000) {
      set.add(item.id);
    }
  }
  return set;
});

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

    <DeviceTable
      :devices="devicesStore.items"
      :online-device-ids="onlineIds"
    />

    <p
      v-if="devicesStore.error"
      class="text-sm text-fm-muted"
    >
      Device API unavailable. Keeping last known data.
    </p>
  </section>
</template>
