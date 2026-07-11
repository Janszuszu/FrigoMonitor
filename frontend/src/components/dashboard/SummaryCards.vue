<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  systemStatus: string;
  totalDevices: number;
  onlineDevices: number;
  activeAlarms: number;
}>();

const statusColor = computed(() => {
  const s = props.systemStatus.toLowerCase();
  if (s === "ok" || s === "healthy" || s === "running") return "text-emerald-400";
  if (s === "warning" || s === "degraded") return "text-amber-400";
  return "text-red-400";
});

const statusDot = computed(() => {
  const s = props.systemStatus.toLowerCase();
  if (s === "ok" || s === "healthy" || s === "running") return "bg-emerald-400";
  if (s === "warning" || s === "degraded") return "bg-amber-400";
  return "bg-red-400";
});

const alarmColor = computed(() => {
  return props.activeAlarms > 0 ? "text-fm-danger" : "text-emerald-400";
});

const alarmDot = computed(() => {
  return props.activeAlarms > 0 ? "bg-fm-danger" : "bg-emerald-400";
});

const onlinePercent = computed(() => {
  if (props.totalDevices === 0) return 0;
  return Math.round((props.onlineDevices / props.totalDevices) * 100);
});
</script>

<template>
  <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
    <!-- SYSTEM STATUS -->
    <article class="rounded-xl border border-slate-700/50 bg-fm-panelSoft/80 p-4 shadow-panel transition hover:border-slate-600/50">
      <div class="mb-3 flex items-center justify-between">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-fm-muted/60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="7" height="7" />
          <rect x="14" y="3" width="7" height="7" />
          <rect x="14" y="14" width="7" height="7" />
          <rect x="3" y="14" width="7" height="7" />
        </svg>
      </div>
      <p class="text-[10px] uppercase tracking-[0.15em] text-fm-muted/60">System Status</p>
      <div class="mt-1 flex items-center gap-2">
        <span class="h-2 w-2 rounded-full" :class="statusDot"></span>
        <p class="text-lg font-bold text-fm-text capitalize" :class="statusColor">
          {{ systemStatus || "—" }}
        </p>
      </div>
      <p class="mt-1 text-[10px] text-fm-muted/40">Backend health</p>
    </article>

    <!-- DEVICES -->
    <article class="rounded-xl border border-slate-700/50 bg-fm-panelSoft/80 p-4 shadow-panel transition hover:border-slate-600/50">
      <div class="mb-3 flex items-center justify-between">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-fm-muted/60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
          <line x1="8" y1="21" x2="16" y2="21" />
          <line x1="12" y1="17" x2="12" y2="21" />
        </svg>
      </div>
      <p class="text-[10px] uppercase tracking-[0.15em] text-fm-muted/60">Devices</p>
      <p class="mt-1 text-lg font-bold text-fm-text">
        {{ totalDevices }}
      </p>
      <p class="mt-1 text-[10px] text-fm-muted/40">Registered devices</p>
    </article>

    <!-- ONLINE DEVICES -->
    <article class="rounded-xl border border-slate-700/50 bg-fm-panelSoft/80 p-4 shadow-panel transition hover:border-slate-600/50">
      <div class="mb-3 flex items-center justify-between">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-fm-muted/60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
      </div>
      <p class="text-[10px] uppercase tracking-[0.15em] text-fm-muted/60">Online Devices</p>
      <p class="mt-1 text-lg font-bold text-emerald-400">
        {{ onlineDevices }}
      </p>
      <p class="mt-1 text-[10px] text-fm-muted/40">
        {{ onlinePercent }}% of total
      </p>
    </article>

    <!-- ALARMS -->
    <article class="rounded-xl border border-slate-700/50 bg-fm-panelSoft/80 p-4 shadow-panel transition hover:border-slate-600/50">
      <div class="mb-3 flex items-center justify-between">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-fm-muted/60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </div>
      <p class="text-[10px] uppercase tracking-[0.15em] text-fm-muted/60">Alarms</p>
      <div class="mt-1 flex items-center gap-2">
        <span class="h-2 w-2 rounded-full" :class="alarmDot"></span>
        <p class="text-lg font-bold" :class="alarmColor">
          {{ activeAlarms }}
        </p>
      </div>
      <p class="mt-1 text-[10px] text-fm-muted/40">
        {{ activeAlarms === 1 ? "Active alarm" : "Active alarms" }}
      </p>
    </article>
  </div>
</template>
