<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  deviceName: string;
  sensorName: string;
  temperature: number | null;
  unit: string | null;
  isOnline: boolean;
  min: number | null;
  max: number | null;
  average: number | null;
  lastUpdate: string | null;
  trend: number | null;
}>();

const displayTemp = computed(() => {
  if (props.temperature === null || props.temperature === undefined) return "—";
  return props.temperature.toFixed(1);
});

const displayUnit = computed(() => {
  return props.unit || "°C";
});

const displayMin = computed(() => {
  if (props.min === null || props.min === undefined) return "—";
  return props.min.toFixed(1);
});

const displayMax = computed(() => {
  if (props.max === null || props.max === undefined) return "—";
  return props.max.toFixed(1);
});

const displayAvg = computed(() => {
  if (props.average === null || props.average === undefined) return "—";
  return props.average.toFixed(1);
});

const displayLastUpdate = computed(() => {
  if (!props.lastUpdate) return "—";
  const d = new Date(props.lastUpdate);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
});

const tempClass = computed(() => {
  if (props.temperature === null || props.temperature === undefined) return "text-fm-muted";
  if (props.temperature > 10) return "text-fm-danger";
  if (props.temperature > 5) return "text-fm-warn";
  return "text-fm-accent";
});

const trendIcon = computed(() => {
  if (props.trend === null || props.trend === undefined) return "";
  if (props.trend > 0) return "↑";
  if (props.trend < 0) return "↓";
  return "→";
});

const trendClass = computed(() => {
  if (props.trend === null || props.trend === undefined) return "text-fm-muted";
  if (props.trend > 0) return "text-fm-danger";
  if (props.trend < 0) return "text-fm-accent";
  return "text-fm-muted";
});

const trendValue = computed(() => {
  if (props.trend === null || props.trend === undefined) return null;
  return `${trendIcon.value} ${Math.abs(props.trend).toFixed(1)}°`;
});
</script>

<template>
  <article class="rounded-xl border border-slate-700/60 bg-gradient-to-br from-fm-panelSoft/90 to-fm-panel/80 p-5 shadow-panel">
    <!-- Header: device - sensor + online/offline -->
    <div class="mb-4 flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0 flex-1">
        <p class="text-[11px] uppercase tracking-[0.15em] text-fm-muted/70 truncate">
          {{ deviceName || "—" }}
        </p>
        <h2 class="mt-0.5 text-base font-semibold text-fm-text truncate">
          {{ sensorName || "—" }}
        </h2>
      </div>
      <span
        class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider"
        :class="isOnline
          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
          : 'border-red-500/40 bg-red-500/10 text-red-400'"
      >
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="isOnline ? 'bg-emerald-400' : 'bg-red-400'"
        ></span>
        {{ isOnline ? "ONLINE" : "OFFLINE" }}
      </span>
    </div>

    <!-- Temperature display -->
    <div class="mb-5 flex items-baseline gap-2">
      <span
        class="text-5xl font-bold tracking-tight md:text-6xl"
        :class="tempClass"
      >
        {{ displayTemp }}
      </span>
      <span class="text-xl font-semibold text-fm-muted/80">
        {{ displayUnit }}
      </span>
      <span
        v-if="trendValue"
        class="ml-1 text-sm font-semibold"
        :class="trendClass"
      >
        {{ trendValue }}
      </span>
    </div>

    <!-- Stats grid -->
    <div class="grid grid-cols-3 gap-3 border-t border-slate-700/40 pt-4">
      <div class="text-center">
        <p class="text-[10px] uppercase tracking-[0.12em] text-fm-muted/60">MIN</p>
        <p class="mt-0.5 text-sm font-bold text-fm-text">{{ displayMin }} {{ displayUnit }}</p>
      </div>
      <div class="text-center">
        <p class="text-[10px] uppercase tracking-[0.12em] text-fm-muted/60">MAX</p>
        <p class="mt-0.5 text-sm font-bold text-fm-text">{{ displayMax }} {{ displayUnit }}</p>
      </div>
      <div class="text-center">
        <p class="text-[10px] uppercase tracking-[0.12em] text-fm-muted/60">AVG</p>
        <p class="mt-0.5 text-sm font-bold text-fm-text">{{ displayAvg }} {{ displayUnit }}</p>
      </div>
    </div>

    <!-- Last update -->
    <div class="mt-3 flex items-center justify-center gap-1.5 text-[10px] text-fm-muted/50">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
      Last update: {{ displayLastUpdate }}
    </div>
  </article>
</template>
