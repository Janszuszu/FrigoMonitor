<script setup lang="ts">
import { onMounted } from "vue";

import Sidebar from "@/components/Sidebar.vue";
import TopBar from "@/components/TopBar.vue";
import { useDevicesStore } from "@/stores/devices";
import { useMeasurementsStore } from "@/stores/measurements";
import { useSensorsStore } from "@/stores/sensors";
import { useSystemStore } from "@/stores/system";

const devicesStore = useDevicesStore();
const measurementsStore = useMeasurementsStore();
const sensorsStore = useSensorsStore();
const systemStore = useSystemStore();

onMounted(async () => {
  try {
    await Promise.all([systemStore.load(), devicesStore.load(), sensorsStore.load(), measurementsStore.load()]);
  } catch (error) {
    console.error("Failed to load system information", error);
  }
  measurementsStore.connect();
});
</script>

<template>
  <div class="min-h-screen bg-fm-bg text-fm-text">
    <div class="flex min-h-screen flex-col md:flex-row">
      <Sidebar />
      <section class="flex min-h-screen flex-1 flex-col">
        <TopBar />
        <main class="flex-1 p-4 md:p-6">
          <RouterView />
        </main>
      </section>
    </div>
  </div>
</template>
