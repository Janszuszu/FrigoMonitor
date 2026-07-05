<script setup lang="ts">
import { computed } from "vue";

type ChartPoint = {
  timestamp: string;
  value: number;
};

const props = withDefaults(
  defineProps<{
    points: ChartPoint[];
    height?: number;
  }>(),
  {
    height: 280,
  },
);

const padding = 28;
const width = 900;

const minMax = computed(() => {
  if (props.points.length === 0) {
    return null;
  }

  let min = props.points[0].value;
  let max = props.points[0].value;
  for (const point of props.points) {
    if (point.value < min) {
      min = point.value;
    }
    if (point.value > max) {
      max = point.value;
    }
  }

  if (min === max) {
    min -= 0.2;
    max += 0.2;
  }

  return { min, max };
});

const normalized = computed(() => {
  if (!minMax.value || props.points.length === 0) {
    return [] as { x: number; y: number; value: number; timestamp: string }[];
  }

  const innerW = width - padding * 2;
  const innerH = props.height - padding * 2;
  const span = minMax.value.max - minMax.value.min;
  const steps = Math.max(1, props.points.length - 1);

  return props.points.map((point, index) => {
    const x = padding + (index / steps) * innerW;
    const y = padding + ((minMax.value.max - point.value) / span) * innerH;
    return { x, y, value: point.value, timestamp: point.timestamp };
  });
});

const pathD = computed(() => {
  if (normalized.value.length === 0) {
    return "";
  }

  return normalized.value
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");
});

const gridLines = computed(() => {
  const lines = 4;
  const innerH = props.height - padding * 2;
  return Array.from({ length: lines + 1 }, (_, i) => padding + (i / lines) * innerH);
});

function formatShortTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "--";
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
</script>

<template>
  <div class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4">
    <svg
      class="h-auto w-full"
      :viewBox="`0 0 ${width} ${height}`"
      role="img"
      aria-label="Sensor trend chart"
      preserveAspectRatio="none"
    >
      <g>
        <line
          v-for="line in gridLines"
          :key="line"
          :x1="padding"
          :y1="line"
          :x2="width - padding"
          :y2="line"
          class="stroke-slate-700/60"
          stroke-width="1"
        />
      </g>

      <path
        v-if="pathD"
        :d="pathD"
        class="fill-none stroke-fm-accent"
        stroke-width="3"
        stroke-linecap="round"
        stroke-linejoin="round"
      />

      <circle
        v-for="point in normalized"
        :key="`${point.timestamp}-${point.x}`"
        :cx="point.x"
        :cy="point.y"
        r="3"
        class="fill-fm-accent"
      >
        <title>{{ point.value.toFixed(2) }} C @ {{ formatShortTime(point.timestamp) }}</title>
      </circle>
    </svg>

    <div class="mt-3 flex items-center justify-between text-xs text-fm-muted">
      <span>{{ normalized[0] ? formatShortTime(normalized[0].timestamp) : "--" }}</span>
      <span>{{ normalized[normalized.length - 1] ? formatShortTime(normalized[normalized.length - 1].timestamp) : "--" }}</span>
    </div>
  </div>
</template>