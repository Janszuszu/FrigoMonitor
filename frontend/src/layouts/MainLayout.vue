<script setup lang="ts">
import { onMounted } from "vue";

import Sidebar from "@/components/Sidebar.vue";
import TopBar from "@/components/TopBar.vue";
import { useMeasurementsStore } from "@/stores/measurements";
import { useSystemStore } from "@/stores/system";

const measurementsStore = useMeasurementsStore();
const systemStore = useSystemStore();

onMounted(async () => {
  try {
    await systemStore.load();
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
