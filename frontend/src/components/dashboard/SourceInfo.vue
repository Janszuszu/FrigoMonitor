<script setup lang="ts">
defineProps<{
  deviceName: string;
  sensorName: string;
  sampleCount: number;
}>();
</script>

<template>
  <article class="rounded-xl border border-slate-700/40 bg-fm-panelSoft/60 p-4 shadow-panel">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-fm-muted/60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <span class="text-[10px] uppercase tracking-[0.15em] text-fm-muted/60">Data Source</span>
      </div>
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fm-muted">
        <span>
          Device: <span class="font-semibold text-fm-text">{{ deviceName || "—" }}</span>
        </span>
        <span>
          Sensor: <span class="font-semibold text-fm-text">{{ sensorName || "—" }}</span>
        </span>
        <span>
          Samples: <span class="font-semibold text-fm-text">{{ sampleCount }}</span>
        </span>
      </div>
    </div>
  </article>
</template>
