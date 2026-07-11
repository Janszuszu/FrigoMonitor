<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from "vue";
import { useMeasurementsStore } from "@/stores/measurements";

defineProps<{
  drawerOpen: boolean;
}>();

const emit = defineEmits<{
  (e: "toggleDrawer"): void;
}>();

const measurementsStore = useMeasurementsStore();

const wsLabel = computed(() => {
  if (measurementsStore.wsState === "connected") return "LIVE";
  if (measurementsStore.wsState === "connecting") return "CONNECTING...";
  return "OFFLINE";
});

const wsClass = computed(() => {
  if (measurementsStore.wsState === "connected") return "bg-emerald-500/15 text-emerald-400 border-emerald-500/40";
  if (measurementsStore.wsState === "connecting") return "bg-amber-500/15 text-amber-400 border-amber-500/40";
  return "bg-red-500/15 text-red-400 border-red-500/40";
});

const wsDotClass = computed(() => {
  if (measurementsStore.wsState === "connected") return "bg-emerald-400";
  if (measurementsStore.wsState === "connecting") return "bg-amber-400";
  return "bg-red-400";
});

// Current clock
const now = ref(new Date());
let clockTimer: number | null = null;

function updateClock(): void {
  now.value = new Date();
}

onMounted(() => {
  clockTimer = window.setInterval(updateClock, 1000);
});

onBeforeUnmount(() => {
  if (clockTimer !== null) {
    window.clearInterval(clockTimer);
    clockTimer = null;
  }
});

const clockTime = computed(() => {
  return now.value.toLocaleTimeString("pl-PL", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
});

const clockDate = computed(() => {
  return now.value.toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
});

function handleRefresh(): void {
  window.location.reload();
}
</script>

<template>
  <header class="flex items-center justify-between border-b border-slate-800/80 bg-fm-panel/95 px-4 py-2.5 backdrop-blur-sm">
    <!-- Left: hamburger + branding -->
    <div class="flex items-center gap-3">
      <button
        type="button"
        class="flex h-9 w-9 items-center justify-center rounded-lg text-fm-muted transition hover:bg-fm-panelSoft hover:text-fm-text focus:outline-none focus-visible:ring-2 focus-visible:ring-fm-accent"
        :aria-label="drawerOpen ? 'Close navigation menu' : 'Open navigation menu'"
        :aria-expanded="drawerOpen"
        @click="emit('toggleDrawer')"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      <!-- Snowflake icon -->
      <svg class="h-5 w-5 text-fm-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2v20M12 2l-3 3M12 2l3 3M12 22l-3-3M12 22l3-3M4.93 4.93l14.14 14.14M4.93 4.93L7.76 7.76M4.93 4.93L2 12M19.07 4.93l-2.83 2.83M19.07 4.93L22 12M4.93 19.07l2.83-2.83M4.93 19.07L2 12M19.07 19.07l-2.83-2.83M19.07 19.07L22 12" />
      </svg>

      <span class="text-sm font-bold uppercase tracking-[0.15em] text-fm-accent md:text-base">
        FrigoMonitor
      </span>
    </div>

    <!-- Right: LIVE indicator + clock + refresh -->
    <div class="flex items-center gap-3">
      <!-- LIVE indicator -->
      <span
        class="flex items-center gap-1.5 rounded-md border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
        :class="wsClass"
      >
        <span class="h-1.5 w-1.5 rounded-full" :class="wsDotClass"></span>
        {{ wsLabel }}
      </span>

      <!-- Clock -->
      <div class="hidden items-center gap-2 text-xs text-fm-muted sm:flex">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <span class="font-mono">{{ clockTime }}</span>
        <span class="text-fm-muted/60">{{ clockDate }}</span>
      </div>

      <!-- Refresh button -->
      <button
        type="button"
        class="flex h-8 w-8 items-center justify-center rounded-lg text-fm-muted transition hover:bg-fm-panelSoft hover:text-fm-text"
        title="Refresh dashboard"
        @click="handleRefresh"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="23 4 23 10 17 10" />
          <polyline points="1 20 1 14 7 14" />
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
        </svg>
      </button>
    </div>
  </header>
</template>
