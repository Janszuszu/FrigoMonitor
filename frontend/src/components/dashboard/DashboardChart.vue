<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from "vue";

type ChartPoint = {
  timestamp: string;
  value: number;
};

const props = withDefaults(
  defineProps<{
    points: ChartPoint[];
    height?: number;
    liveMode?: boolean;
    sensorLabel?: string;
    fullscreen?: boolean;
    alarmLow?: number | null;
    alarmHigh?: number | null;
  }>(),
  {
    height: 300,
    liveMode: false,
    sensorLabel: "",
    fullscreen: false,
    alarmLow: null,
    alarmHigh: null,
  },
);

const emit = defineEmits<{
  (e: "toggleFullscreen"): void;
}>();

type ParsedPoint = {
  t: number;
  timestamp: string;
  value: number;
};

const padding = 48;
const rightPadding = 16;
const width = 960;
const MAX_RENDER_POINTS = 1200;
const MIN_ZOOM_SPAN_MS = 30 * 1000;

const svgRef = ref<SVGSVGElement | null>(null);
const containerRef = ref<HTMLDivElement | null>(null);
const containerWidth = ref(width);

const viewFrom = ref<number | null>(null);
const viewTo = ref<number | null>(null);

const hoverState = ref<{ x: number; y: number; point: ParsedPoint } | null>(null);
const isDragging = ref(false);
const dragStartX = ref(0);
const dragStartFrom = ref(0);
const dragStartTo = ref(0);

let resizeObserver: ResizeObserver | null = null;

function updateContainerWidth(): void {
  if (containerRef.value) {
    containerWidth.value = containerRef.value.clientWidth || width;
  }
}

onMounted(() => {
  updateContainerWidth();
  resizeObserver = new ResizeObserver(() => {
    updateContainerWidth();
  });
  if (containerRef.value) {
    resizeObserver.observe(containerRef.value);
  }
});

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});

const parsedPoints = computed<ParsedPoint[]>(() => {
  const valid = props.points
    .map((point) => ({
      t: new Date(point.timestamp).getTime(),
      timestamp: point.timestamp,
      value: point.value,
    }))
    .filter((point) => Number.isFinite(point.t) && Number.isFinite(point.value));

  valid.sort((a, b) => a.t - b.t);
  return valid;
});

const fullDomain = computed<{ from: number; to: number; min: number; max: number } | null>(() => {
  if (parsedPoints.value.length === 0) return null;

  let min = parsedPoints.value[0].value;
  let max = parsedPoints.value[0].value;

  for (const point of parsedPoints.value) {
    if (point.value < min) min = point.value;
    if (point.value > max) max = point.value;
  }

  // Include alarm thresholds in value range
  if (props.alarmLow !== null && props.alarmLow !== undefined) {
    min = Math.min(min, props.alarmLow);
  }
  if (props.alarmHigh !== null && props.alarmHigh !== undefined) {
    max = Math.max(max, props.alarmHigh);
  }

  if (min === max) {
    min -= 0.5;
    max += 0.5;
  }

  // Add padding
  const valuePad = (max - min) * 0.1;
  min -= valuePad;
  max += valuePad;

  const from = parsedPoints.value[0].t;
  const to = parsedPoints.value[parsedPoints.value.length - 1].t;
  return { from, to, min, max };
});

const isZoomed = computed(() => {
  if (!fullDomain.value || viewFrom.value === null || viewTo.value === null) return false;
  return viewFrom.value > fullDomain.value.from || viewTo.value < fullDomain.value.to;
});

watch(
  [parsedPoints, () => props.liveMode],
  () => {
    if (!fullDomain.value) {
      viewFrom.value = null;
      viewTo.value = null;
      hoverState.value = null;
      return;
    }
    if (!isZoomed.value || props.liveMode) {
      viewFrom.value = fullDomain.value.from;
      viewTo.value = fullDomain.value.to;
    }
  },
  { immediate: true },
);

const activeDomain = computed(() => {
  if (!fullDomain.value) return null;
  if (viewFrom.value === null || viewTo.value === null) {
    return { from: fullDomain.value.from, to: fullDomain.value.to };
  }
  const from = Math.max(fullDomain.value.from, Math.min(viewFrom.value, fullDomain.value.to));
  const to = Math.min(fullDomain.value.to, Math.max(viewTo.value, fullDomain.value.from));
  return { from, to };
});

const visiblePoints = computed(() => {
  if (!activeDomain.value) return [] as ParsedPoint[];
  return parsedPoints.value.filter((point) => point.t >= activeDomain.value!.from && point.t <= activeDomain.value!.to);
});

function downsampleMinMax(points: ParsedPoint[], targetPoints: number): ParsedPoint[] {
  if (points.length <= targetPoints) return points;
  const bucketCount = Math.max(1, Math.floor(targetPoints / 2));
  const bucketSize = Math.max(1, Math.ceil(points.length / bucketCount));
  const sampled: ParsedPoint[] = [];
  for (let start = 0; start < points.length; start += bucketSize) {
    const bucket = points.slice(start, start + bucketSize);
    if (!bucket.length) continue;
    if (bucket.length === 1) { sampled.push(bucket[0]); continue; }
    let min = bucket[0], max = bucket[0];
    for (const point of bucket) {
      if (point.value < min.value) min = point;
      if (point.value > max.value) max = point;
    }
    if (min.t <= max.t) { sampled.push(min, max); } else { sampled.push(max, min); }
  }
  sampled.sort((a, b) => a.t - b.t);
  return sampled.slice(0, targetPoints);
}

const sampledVisiblePoints = computed(() => downsampleMinMax(visiblePoints.value, MAX_RENDER_POINTS));

const chartHeight = computed(() => props.fullscreen ? Math.max(400, containerWidth.value * 0.5) : props.height);

const normalized = computed(() => {
  if (!activeDomain.value || !fullDomain.value || sampledVisiblePoints.value.length === 0) return [] as Array<ParsedPoint & { x: number; y: number }>;

  const innerW = width - padding - rightPadding;
  const innerH = chartHeight.value - padding * 2;
  const timeSpan = Math.max(1, activeDomain.value.to - activeDomain.value.from);
  const valueSpan = fullDomain.value.max - fullDomain.value.min;

  return sampledVisiblePoints.value.map((point) => {
    const x = padding + ((point.t - activeDomain.value!.from) / timeSpan) * innerW;
    const y = padding + ((fullDomain.value!.max - point.value) / valueSpan) * innerH;
    return { ...point, x, y };
  });
});

const pathD = computed(() => {
  if (normalized.value.length === 0) return "";
  return normalized.value
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");
});

// Y axis ticks - dynamic based on value range
const yTicks = computed(() => {
  if (!fullDomain.value) return [];
  const range = fullDomain.value.max - fullDomain.value.min;
  const step = Math.pow(10, Math.floor(Math.log10(range)));
  const niceStep = step / (range / step > 3 ? 1 : 2);
  const ticks: number[] = [];
  const start = Math.ceil(fullDomain.value.min / niceStep) * niceStep;
  for (let v = start; v <= fullDomain.value.max; v += niceStep) {
    ticks.push(Math.round(v * 100) / 100);
  }
  return ticks;
});

const gridLines = computed(() => {
  if (!fullDomain.value) return [];
  const innerH = chartHeight.value - padding * 2;
  const valueSpan = fullDomain.value.max - fullDomain.value.min;
  return yTicks.value.map((tick) => ({
    value: tick,
    y: padding + ((fullDomain.value!.max - tick) / valueSpan) * innerH,
  }));
});

// Alarm threshold lines
const alarmLowY = computed(() => {
  if (props.alarmLow === null || props.alarmLow === undefined || !fullDomain.value) return null;
  const innerH = chartHeight.value - padding * 2;
  const valueSpan = fullDomain.value.max - fullDomain.value.min;
  return padding + ((fullDomain.value.max - props.alarmLow) / valueSpan) * innerH;
});

const alarmHighY = computed(() => {
  if (props.alarmHigh === null || props.alarmHigh === undefined || !fullDomain.value) return null;
  const innerH = chartHeight.value - padding * 2;
  const valueSpan = fullDomain.value.max - fullDomain.value.min;
  return padding + ((fullDomain.value.max - props.alarmHigh) / valueSpan) * innerH;
});

// X axis time labels
const xLabels = computed(() => {
  if (!activeDomain.value) return [];
  const span = activeDomain.value.to - activeDomain.value.from;
  const count = Math.min(8, Math.max(3, Math.floor(containerWidth.value / 120)));
  const labels: { x: number; text: string }[] = [];
  const innerW = width - padding - rightPadding;
  for (let i = 0; i <= count; i++) {
    const t = activeDomain.value.from + (span / count) * i;
    const x = padding + (i / count) * innerW;
    const d = new Date(t);
    let text: string;
    if (span <= 3600000) {
      text = d.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } else if (span <= 86400000) {
      text = d.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
    } else {
      text = d.toLocaleString("pl-PL", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    }
    labels.push({ x, text });
  }
  return labels;
});

function formatShortTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("pl-PL", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function formatTooltipDate(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("pl-PL", {
    weekday: "short", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function resetZoom(): void {
  if (!fullDomain.value) return;
  viewFrom.value = fullDomain.value.from;
  viewTo.value = fullDomain.value.to;
}

function clampDomain(from: number, to: number): { from: number; to: number } | null {
  if (!fullDomain.value) return null;
  let nextFrom = from, nextTo = to;
  let span = nextTo - nextFrom;
  if (span < MIN_ZOOM_SPAN_MS) {
    const center = (nextFrom + nextTo) / 2;
    nextFrom = center - MIN_ZOOM_SPAN_MS / 2;
    nextTo = center + MIN_ZOOM_SPAN_MS / 2;
    span = nextTo - nextFrom;
  }
  const fullSpan = fullDomain.value.to - fullDomain.value.from;
  if (span > fullSpan) return { from: fullDomain.value.from, to: fullDomain.value.to };
  if (nextFrom < fullDomain.value.from) { nextTo += fullDomain.value.from - nextFrom; nextFrom = fullDomain.value.from; }
  if (nextTo > fullDomain.value.to) { nextFrom -= nextTo - fullDomain.value.to; nextTo = fullDomain.value.to; }
  nextFrom = Math.max(fullDomain.value.from, nextFrom);
  nextTo = Math.min(fullDomain.value.to, nextTo);
  return { from: nextFrom, to: nextTo };
}

function xToTimestamp(clientX: number): number | null {
  if (!svgRef.value || !activeDomain.value) return null;
  const bounds = svgRef.value.getBoundingClientRect();
  const innerW = width - padding - rightPadding;
  if (bounds.width <= 0 || innerW <= 0) return null;
  const localX = ((clientX - bounds.left) / bounds.width) * width;
  const clampedX = Math.max(padding, Math.min(width - rightPadding, localX));
  const ratio = (clampedX - padding) / innerW;
  return activeDomain.value.from + ratio * (activeDomain.value.to - activeDomain.value.from);
}

function onWheel(event: WheelEvent): void {
  if (!activeDomain.value || !fullDomain.value) return;
  const centerT = xToTimestamp(event.clientX);
  if (centerT === null) return;
  const zoomFactor = event.deltaY > 0 ? 1.18 : 0.82;
  const span = activeDomain.value.to - activeDomain.value.from;
  const nextSpan = span * zoomFactor;
  const ratioLeft = (centerT - activeDomain.value.from) / Math.max(1, span);
  const nextFrom = centerT - nextSpan * ratioLeft;
  const nextTo = nextFrom + nextSpan;
  const clamped = clampDomain(nextFrom, nextTo);
  if (clamped) { viewFrom.value = clamped.from; viewTo.value = clamped.to; }
}

function onPointerDown(event: PointerEvent): void {
  if (event.button !== 0 || !activeDomain.value) return;
  isDragging.value = true;
  dragStartX.value = event.clientX;
  dragStartFrom.value = activeDomain.value.from;
  dragStartTo.value = activeDomain.value.to;
  svgRef.value?.setPointerCapture(event.pointerId);
}

function onPointerMove(event: PointerEvent): void {
  if (!svgRef.value) return;
  const bounds = svgRef.value.getBoundingClientRect();
  if (bounds.width <= 0) return;
  const localX = ((event.clientX - bounds.left) / bounds.width) * width;
  const localY = ((event.clientY - bounds.top) / bounds.height) * chartHeight.value;

  if (isDragging.value && fullDomain.value) {
    const span = dragStartTo.value - dragStartFrom.value;
    const deltaMs = ((event.clientX - dragStartX.value) / Math.max(1, bounds.width)) * span;
    const clamped = clampDomain(dragStartFrom.value - deltaMs, dragStartTo.value - deltaMs);
    if (clamped) { viewFrom.value = clamped.from; viewTo.value = clamped.to; }
    return;
  }

  if (!normalized.value.length) { hoverState.value = null; return; }

  let nearest = normalized.value[0];
  let bestDistance = Math.abs(nearest.x - localX);
  for (const point of normalized.value) {
    const distance = Math.abs(point.x - localX);
    if (distance < bestDistance) { bestDistance = distance; nearest = point; }
  }

  hoverState.value = { x: nearest.x, y: nearest.y, point: { t: nearest.t, value: nearest.value, timestamp: nearest.timestamp } };

  if (localY < padding || localY > chartHeight.value - padding) hoverState.value = null;
}

function onPointerUp(event: PointerEvent): void {
  if (!isDragging.value) return;
  isDragging.value = false;
  svgRef.value?.releasePointerCapture(event.pointerId);
}

function onPointerLeave(): void {
  if (!isDragging.value) hoverState.value = null;
}

// Latest value marker
const latestPoint = computed(() => {
  if (normalized.value.length === 0) return null;
  return normalized.value[normalized.value.length - 1];
});
</script>

<template>
  <div
    ref="containerRef"
    class="rounded-xl border border-slate-700/50 bg-fm-panelSoft/80 p-4 shadow-panel"
    :class="{ 'flex-1 flex flex-col': fullscreen }"
  >
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-fm-muted">
      <div class="flex items-center gap-2">
        <span class="uppercase tracking-[0.12em]">{{ liveMode ? "Live Stream" : "Historical Range" }}</span>
        <span v-if="sensorLabel" class="text-fm-text/80">{{ sensorLabel }}</span>
      </div>
      <div class="flex items-center gap-2">
        <button
          v-if="isZoomed"
          type="button"
          class="rounded-md border border-slate-600/60 bg-slate-900/80 px-3 py-1 font-semibold text-fm-text hover:border-fm-accent/60"
          @click="resetZoom"
        >
          Reset zoom
        </button>
        <button
          type="button"
          class="rounded-md border border-slate-600/60 bg-slate-900/80 px-2 py-1 text-fm-muted hover:border-fm-accent/60 hover:text-fm-text"
          :title="fullscreen ? 'Exit fullscreen' : 'Fullscreen'"
          @click="emit('toggleFullscreen')"
        >
          <svg v-if="!fullscreen" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" /><line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="4 14 10 14 10 20" /><polyline points="20 10 14 10 14 4" /><line x1="14" y1="10" x2="21" y2="3" /><line x1="3" y1="21" x2="10" y2="14" />
          </svg>
        </button>
      </div>
    </div>

    <div class="relative flex-1">
      <svg
        ref="svgRef"
        class="h-auto w-full"
        :viewBox="`0 0 ${width} ${chartHeight}`"
        role="img"
        aria-label="Temperature trend chart"
        preserveAspectRatio="xMidYMid meet"
        @wheel.prevent="onWheel"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @pointerleave="onPointerLeave"
      >
        <!-- Grid lines -->
        <g>
          <line
            v-for="gl in gridLines"
            :key="gl.value"
            :x1="padding"
            :y1="gl.y"
            :x2="width - rightPadding"
            :y2="gl.y"
            class="stroke-slate-700/40"
            stroke-width="1"
          />
        </g>

        <!-- Y axis labels -->
        <g class="text-[10px] fill-fm-muted/60">
          <text
            v-for="gl in gridLines"
            :key="'label-' + gl.value"
            :x="padding - 8"
            :y="gl.y + 3.5"
            text-anchor="end"
          >{{ gl.value > 0 ? '+' : '' }}{{ gl.value }}°</text>
        </g>

        <!-- X axis labels -->
        <g class="text-[10px] fill-fm-muted/50">
          <text
            v-for="(label, i) in xLabels"
            :key="'xlabel-' + i"
            :x="label.x"
            :y="chartHeight - 6"
            text-anchor="middle"
          >{{ label.text }}</text>
        </g>

        <!-- Alarm HIGH threshold line -->
        <g v-if="alarmHighY !== null">
          <line
            :x1="padding"
            :y1="alarmHighY"
            :x2="width - rightPadding"
            :y2="alarmHighY"
            class="stroke-fm-danger/50"
            stroke-width="1.5"
            stroke-dasharray="6,4"
          />
          <rect
            :x="width - rightPadding - 62"
            :y="alarmHighY - 11"
            width="62"
            height="14"
            rx="3"
            class="fill-fm-danger/20"
          />
          <text
            :x="width - rightPadding - 4"
            :y="alarmHighY - 1"
            text-anchor="end"
            class="fill-fm-danger/80 text-[9px] font-semibold"
          >ALARM HIGH</text>
        </g>

        <!-- Alarm LOW threshold line -->
        <g v-if="alarmLowY !== null">
          <line
            :x1="padding"
            :y1="alarmLowY"
            :x2="width - rightPadding"
            :y2="alarmLowY"
            class="stroke-fm-warn/50"
            stroke-width="1.5"
            stroke-dasharray="6,4"
          />
          <rect
            :x="width - rightPadding - 60"
            :y="alarmLowY - 11"
            width="60"
            height="14"
            rx="3"
            class="fill-fm-warn/20"
          />
          <text
            :x="width - rightPadding - 4"
            :y="alarmLowY - 1"
            text-anchor="end"
            class="fill-fm-warn/80 text-[9px] font-semibold"
          >ALARM LOW</text>
        </g>

        <!-- Hover crosshair -->
        <line
          v-if="hoverState"
          :x1="hoverState.x"
          :y1="padding"
          :x2="hoverState.x"
          :y2="chartHeight - padding"
          class="stroke-fm-accent/30"
          stroke-width="1"
        />

        <!-- Temperature line -->
        <path
          v-if="pathD"
          :d="pathD"
          class="fill-none stroke-fm-accent"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />

        <!-- Data points -->
        <circle
          v-for="point in normalized"
          :key="`${point.timestamp}-${point.x}`"
          :cx="point.x"
          :cy="point.y"
          :r="normalized.length < 320 ? 2 : 0"
          class="fill-fm-accent/80"
        >
          <title>{{ point.value.toFixed(2) }} °C @ {{ formatShortTime(point.timestamp) }}</title>
        </circle>

        <!-- Latest value marker -->
        <g v-if="latestPoint && !hoverState">
          <circle
            :cx="latestPoint.x"
            :cy="latestPoint.y"
            r="4"
            class="fill-fm-accent stroke-fm-panelSoft"
            stroke-width="2"
          />
          <rect
            :x="latestPoint.x + 8"
            :y="latestPoint.y - 10"
            :width="`${latestPoint.value.toFixed(1).length * 8 + 20}`"
            height="20"
            rx="4"
            class="fill-slate-900/90 stroke-fm-accent/40"
            stroke-width="1"
          />
          <text
            :x="latestPoint.x + 14"
            :y="latestPoint.y + 4"
            class="fill-fm-accent text-[10px] font-bold"
          >{{ latestPoint.value.toFixed(1) }}°</text>
        </g>

        <!-- Hover dot -->
        <circle
          v-if="hoverState"
          :cx="hoverState.x"
          :cy="hoverState.y"
          r="4"
          class="fill-fm-accent stroke-fm-panelSoft"
          stroke-width="2"
        />
      </svg>

      <!-- Tooltip -->
      <div
        v-if="hoverState"
        class="pointer-events-none absolute z-10 max-w-[300px] rounded-md border border-slate-700/60 bg-slate-950/95 px-3 py-2 text-xs text-fm-text shadow-panel"
        :style="{
          left: `${Math.max(8, Math.min(hoverState.x / width * 100, 82))}%`,
          top: `${Math.max(6, (hoverState.y / chartHeight * 100) - 22)}%`
        }"
      >
        <div class="font-semibold text-fm-accent">
          {{ hoverState.point.value.toFixed(2) }} °C
        </div>
        <div class="mt-0.5 text-fm-muted">
          {{ formatTooltipDate(hoverState.point.timestamp) }}
        </div>
      </div>
    </div>

    <div class="mt-3 flex flex-wrap items-center justify-between gap-2 text-[10px] text-fm-muted/50">
      <span>Scroll: zoom | Drag: pan</span>
      <span>{{ normalized[0] ? formatShortTime(normalized[0].timestamp) : "--" }}</span>
      <span>{{ normalized[normalized.length - 1] ? formatShortTime(normalized[normalized.length - 1].timestamp) : "--" }}</span>
    </div>
  </div>
</template>
