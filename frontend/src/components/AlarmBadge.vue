<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  severity: string;
}>();

const badgeClass = computed(() => {
  if (props.severity.toLowerCase().includes("critical") || props.severity.toLowerCase().includes("high")) {
    return "border-fm-danger/60 bg-fm-danger/20 text-fm-danger";
  }
  if (props.severity.toLowerCase().includes("medium") || props.severity.toLowerCase().includes("warn")) {
    return "border-fm-warn/60 bg-fm-warn/20 text-fm-warn";
  }
  return "border-slate-700 bg-slate-800/70 text-fm-muted";
});
</script>

<template>
  <span
    class="rounded-full border px-2 py-1 text-xs font-semibold uppercase"
    :class="badgeClass"
  >
    {{ severity }}
  </span>
</template>
