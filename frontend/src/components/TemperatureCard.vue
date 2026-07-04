<script setup lang="ts">
defineProps<{
  sensor: string;
  device: string;
  value: number | null | undefined;
  timestamp: string | null | undefined;
}>();

function formatTemperature(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(1)} C`;
}

function formatTime(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return "No data";
  }
  return new Date(timestamp).toLocaleString();
}
</script>

<template>
  <article class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4">
    <p class="text-xs uppercase tracking-[0.16em] text-fm-muted">
      {{ device }}
    </p>
    <h3 class="mt-1 text-base font-semibold text-fm-text">
      {{ sensor }}
    </h3>
    <p class="mt-3 text-2xl font-bold text-fm-accent">
      {{ formatTemperature(value) }}
    </p>
    <p class="mt-2 text-xs text-fm-muted">
      {{ formatTime(timestamp) }}
    </p>
  </article>
</template>
