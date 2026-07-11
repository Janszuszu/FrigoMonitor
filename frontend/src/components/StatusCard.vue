<script setup lang="ts">
defineProps<{
  label: string;
  value: string | number;
  alarm?: boolean;
  activeAlarms?: number;
}>();
</script>

<template>
  <article
    class="rounded-lg border shadow-panel"
    :class="alarm && activeAlarms && activeAlarms > 0
      ? 'border-red-700 bg-red-900/70'
      : 'border-slate-800 bg-fm-panelSoft'"
  >
    <div class="px-3 py-2.5">
      <p
        class="text-xs uppercase tracking-[0.16em]"
        :class="alarm && activeAlarms && activeAlarms > 0 ? 'text-red-200' : 'text-fm-muted'"
      >
        {{ label }}
      </p>
      <p
        class="mt-1 text-2xl font-bold"
        :class="alarm && activeAlarms && activeAlarms > 0 ? 'text-red-50' : 'text-fm-text'"
      >
        {{ value }}
      </p>
    </div>
  </article>
</template>
