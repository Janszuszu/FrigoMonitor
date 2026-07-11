<script setup lang="ts">
import { computed } from "vue";
import { useDevicesStore } from "@/stores/devices";
import { useSensorsStore } from "@/stores/sensors";

const props = defineProps<{
  modelValue: number | null;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: number | null): void;
}>();

const devicesStore = useDevicesStore();
const sensorsStore = useSensorsStore();

const deviceById = computed(() => new Map(devicesStore.items.map((d) => [d.id, d])));

const options = computed(() => {
  return sensorsStore.items.map((sensor) => {
    const device = deviceById.value.get(sensor.device_id);
    return {
      id: sensor.id,
      label: `${device?.display_name || device?.name || "Unknown"} - ${sensor.name || `Sensor ${sensor.id}`}`,
    };
  });
});

function onChange(event: Event): void {
  const target = event.target as HTMLSelectElement;
  const val = target.value ? Number(target.value) : null;
  emit("update:modelValue", val);
}
</script>

<template>
  <div class="relative">
    <select
      :value="modelValue ?? ''"
      class="w-full appearance-none rounded-lg border border-slate-700/80 bg-slate-900/90 px-3 py-2 pr-8 text-xs text-fm-text outline-none transition focus:border-fm-accent/60 focus:ring-1 focus:ring-fm-accent/30"
      @change="onChange"
    >
      <option
        v-if="!options.length"
        value=""
        disabled
      >
        No sensors available
      </option>
      <option
        v-for="opt in options"
        :key="opt.id"
        :value="opt.id"
      >
        {{ opt.label }}
      </option>
    </select>
    <svg
      class="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fm-muted"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  </div>
</template>
