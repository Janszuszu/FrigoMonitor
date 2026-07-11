<script setup lang="ts">
import { computed } from "vue";

import { useMeasurementsStore } from "@/stores/measurements";
import { useSystemStore } from "@/stores/system";

const measurementsStore = useMeasurementsStore();
const systemStore = useSystemStore();

const wsLabel = computed(() => {
  if (measurementsStore.wsState === "connected") {
    return "Connected";
  }
  if (measurementsStore.wsState === "connecting") {
    return "Connecting...";
  }
  return "Disconnected";
});

const wsClass = computed(() => {
  if (measurementsStore.wsState === "connected") {
    return "bg-fm-success/20 text-fm-success border-fm-success/50";
  }
  if (measurementsStore.wsState === "connecting") {
    return "bg-fm-warn/20 text-fm-warn border-fm-warn/50";
  }
  return "bg-fm-danger/20 text-fm-danger border-fm-danger/50";
});
</script>

<template>
  <header class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 bg-fm-panel p-4 md:p-6">
    <div class="flex items-center gap-3">
      <span
        class="rounded-md border px-3 py-1 text-xs font-semibold uppercase tracking-wide"
        :class="wsClass"
      >
        {{ wsLabel }}
      </span>
      <span class="rounded-md border border-slate-700 px-3 py-1 text-xs font-semibold text-fm-muted">
        {{ systemStore.health?.status || "unknown" }}
      </span>
    </div>
  </header>
</template>
