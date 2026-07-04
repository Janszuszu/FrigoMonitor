<script setup lang="ts">
defineProps<{
  label: string;
  value: string | number;
}>();
</script>

<template>
  <article class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4 shadow-panel">
    <p class="text-xs uppercase tracking-[0.16em] text-fm-muted">
      {{ label }}
    </p>
    <p class="mt-2 text-3xl font-bold text-fm-text">
      {{ value }}
    </p>
  </article>
</template>
