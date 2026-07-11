<script setup lang="ts">
import { computed } from "vue";

import { useAlarmsStore } from "@/stores/alarms";
import { useDevicesStore } from "@/stores/devices";
import { useMeasurementsStore } from "@/stores/measurements";
import { useSystemStore } from "@/stores/system";

defineProps<{
  drawerOpen: boolean;
}>();

const emit = defineEmits<{
  (e: "toggleDrawer"): void;
}>();

const measurementsStore = useMeasurementsStore();
const systemStore = useSystemStore();
const devicesStore = useDevicesStore();
const alarmsStore = useAlarmsStore();

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

const alarmClass = computed(() => {
  return alarmsStore.count > 0
    ? "bg-red-900/70 text-red-200 border-red-700"
    : "border-slate-700 text-fm-muted";
});
</script>

<template>
  <header class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 bg-fm-panel px-3 py-2 md:px-4 md:py-2.5">
    <div class="flex items-center gap-3">
      <button
        type="button"
        class="flex h-9 w-9 items-center justify-center rounded-md text-fm-muted transition hover:bg-fm-panelSoft hover:text-fm-text focus:outline-none focus-visible:ring-2 focus-visible:ring-fm-accent"
        :aria-label="drawerOpen ? 'Close navigation menu' : 'Open navigation menu'"
        :aria-expanded="drawerOpen"
        @click="emit('toggleDrawer')"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          class="h-5 w-5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      <span class="text-sm font-bold uppercase tracking-[0.15em] text-fm-accent md:text-base">
        FrigoMonitor
      </span>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <span
        class="rounded-md border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
        :class="wsClass"
      >
        {{ wsLabel }}
      </span>

      <span class="rounded-md border border-slate-700 px-2.5 py-0.5 text-[11px] font-semibold text-fm-muted">
        {{ systemStore.health?.status || "unknown" }}
      </span>

      <span class="rounded-md border border-slate-700 px-2.5 py-0.5 text-[11px] font-semibold text-fm-muted">
        {{ devicesStore.items.length }}
      </span>

      <span class="rounded-md border border-slate-700 px-2.5 py-0.5 text-[11px] font-semibold text-fm-muted">
        {{ devicesStore.onlineCount }}
      </span>

      <span
        class="rounded-md border px-2.5 py-0.5 text-[11px] font-semibold transition-colors"
        :class="alarmClass"
      >
        {{ alarmsStore.count }}
      </span>
    </div>
  </header>
</template>
