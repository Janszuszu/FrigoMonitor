<script setup lang="ts">
import { onMounted, ref } from "vue";

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

const drawerOpen = ref(false);

function toggleDrawer(): void {
  drawerOpen.value = !drawerOpen.value;
}

function closeDrawer(): void {
  drawerOpen.value = false;
}

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
    <Sidebar
      :open="drawerOpen"
      @close="closeDrawer"
    />
    <div class="flex min-h-screen flex-col">
      <TopBar
        :drawer-open="drawerOpen"
        @toggle-drawer="toggleDrawer"
      />
      <main class="flex-1 p-3 md:p-4">
        <RouterView />
      </main>
    </div>
  </div>
</template>
