<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from "vue";

type ChartPoint = {
  timestamp: string;
  value: number;
};

type Thresholds = {
  min: number | null;
  max: number | null;
};

const props = withDefaults(
  defineProps<{
    points: ChartPoint[];
    height?: number;
    liveMode?: boolean;
    sensorLabel?: string;
    fullscreen?: boolean;
    thresholds?: Thresholds | null;
  }>(),
  {
    height: 300,
    liveMode: false,
    sensorLabel: "",
    fullscreen: false,
    thresholds: null,
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

const padding = { top: 16, right: 16, bottom: 40, left: 52 };
const width = 960;
const MAX_RENDER_POINTS = 1200;
const MIN_ZOOM_SPAN_MS = 30 * 1000;

const svgRef = ref<SVGSVGElement | null>(null);
const containerRef = ref<HTMLDivElement | null>(null);
const containerWidth = ref(width);

const viewFrom = ref<number | null>(null);
const viewTo = ref<number | null>(null);

const hoverState = ref<{ x: number; y: number; point: ParsedPoint; barIndex: number } | null>(null);
const isDragging = ref(false);
const dragStartX = ref(0);
const dragStartFrom = ref(0);
const dragStartTo = ref(0);

// ResizeObserver for responsive chart
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

const fullDomain = computed(() => {
  if (parsedPoints.value.length === 0) {
    return null;
  }

  let minV = parsedPoints.value[0].value;
  let maxV = parsedPoints.value[0].value;

  for (const point of parsedPoints.value) {
    if (point.value < minV) {
      minV = point.value;
    }
    if (point.value > maxV) {
      maxV = point.value;
    }
  }

  if (minV === maxV) {
    minV -= 0.2;
    maxV += 0.2;
  }

  const from = parsedPoints.value[0].t;
  const to = parsedPoints.value[parsedPoints.value.length - 1].t;
  return { from, to, minV, maxV };
});

const isZoomed = computed(() => {
  if (!fullDomain.value || viewFrom.value === null || viewTo.value === null) {
    return false;
  }
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
  if (!fullDomain.value) {
    return null;
  }

  if (viewFrom.value === null || viewTo.value === null) {
    return { from: fullDomain.value.from, to: fullDomain.value.to };
  }

  const from = Math.max(fullDomain.value.from, Math.min(viewFrom.value, fullDomain.value.to));
  const to = Math.min(fullDomain.value.to, Math.max(viewTo.value, fullDomain.value.from));
  return { from, to };
});

const visiblePoints = computed(() => {
  if (!activeDomain.value) {
    return [] as ParsedPoint[];
  }

  return parsedPoints.value.filter((point) => point.t >= activeDomain.value!.from && point.t <= activeDomain.value!.to);
});

function downsampleMinMax(points: ParsedPoint[], targetPoints: number): ParsedPoint[] {
  if (points.length <= targetPoints) {
    return points;
  }

  const bucketCount = Math.max(1, Math.floor(targetPoints / 2));
  const bucketSize = Math.max(1, Math.ceil(points.length / bucketCount));
  const sampled: ParsedPoint[] = [];

  for (let start = 0; start < points.length; start += bucketSize) {
    const bucket = points.slice(start, start + bucketSize);
    if (!bucket.length) {
      continue;
    }

    if (bucket.length === 1) {
      sampled.push(bucket[0]);
      continue;
    }

    let min = bucket[0];
    let max = bucket[0];
    for (const point of bucket) {
      if (point.value < min.value) {
        min = point;
      }
      if (point.value > max.value) {
        max = point;
      }
    }

    if (min.t <= max.t) {
      sampled.push(min, max);
    } else {
      sampled.push(max, min);
    }
  }

  sampled.sort((a, b) => a.t - b.t);
  return sampled.slice(0, targetPoints);
}

const sampledVisiblePoints = computed(() => downsampleMinMax(visiblePoints.value, MAX_RENDER_POINTS));

// ─── Dynamic value range based on data + thresholds ───
const valueRange = computed(() => {
  const pts = sampledVisiblePoints.value;
  if (pts.length === 0) {
    return { min: -30, max: 40 };
  }

  let minV = pts[0].value;
  let maxV = pts[0].value;
  for (const p of pts) {
    if (p.value < minV) minV = p.value;
    if (p.value > maxV) maxV = p.value;
  }

  // Include thresholds in range
  const th = props.thresholds;
  if (th) {
    if (th.min !== null && th.min < minV) minV = th.min;
    if (th.max !== null && th.max > maxV) maxV = th.max;
  }

  // Add padding
  const pad = Math.max(2, (maxV - minV) * 0.15);
  minV -= pad;
  maxV += pad;

  // Ensure minimum span
  if (maxV - minV < 1) {
    minV -= 2;
    maxV += 2;
  }

  return { min: minV, max: maxV };
});

const chartHeight = computed(() => props.fullscreen ? Math.max(400, containerWidth.value * 0.5) : props.height);

const innerWidth = computed(() => width - padding.left - padding.right);
const innerHeight = computed(() => chartHeight.value - padding.top - padding.bottom);

// ─── Bar color logic ───
function getBarColor(value: number): string {
  const th = props.thresholds;
  if (!th) {
    return "#4dd0e1"; // cyan default
  }

  const { min, max } = th;

  // If both thresholds exist
  if (min !== null && max !== null) {
    const normalRange = max - min;
    const warningZone = normalRange * 0.2; // upper 20% of range
    const warningThreshold = max - warningZone;

    if (value < min) return "#42a5f5"; // blue - too cold
    if (value >= max) return "#ef5350"; // red - too hot
    if (value >= warningThreshold) return "#f9a825"; // orange - approaching max
    return "#26c6da"; // cyan - normal
  }

  // Only min threshold exists
  if (min !== null) {
    if (value < min) return "#42a5f5"; // blue - too cold
    const warningZone = Math.abs(min) * 0.15 || 2;
    if (value > min + warningZone * 3) return "#ef5350"; // red - far above min
    if (value > min + warningZone) return "#f9a825"; // orange - above min
    return "#26c6da"; // cyan - near min
  }

  // Only max threshold exists
  if (max !== null) {
    if (value >= max) return "#ef5350"; // red - too hot
    const warningZone = Math.abs(max) * 0.15 || 2;
    const warningThreshold = max - warningZone;
    if (value >= warningThreshold) return "#f9a825"; // orange - approaching max
    return "#26c6da"; // cyan - normal
  }

  return "#4dd0e1"; // fallback cyan
}

// ─── Normalized bar positions ───
const bars = computed(() => {
  const pts = sampledVisiblePoints.value;
  if (pts.length === 0 || !activeDomain.value) return [];

  const timeSpan = Math.max(1, activeDomain.value.to - activeDomain.value.from);
  const valSpan = valueRange.value.max - valueRange.value.min;
  const iw = innerWidth.value;
  const ih = innerHeight.value;

  // Calculate bar width: fill available space with minimal gaps
  const totalBarArea = iw;
  const gapRatio = pts.length > 100 ? 0.1 : pts.length > 50 ? 0.15 : 0.2;
  const totalGaps = totalBarArea * gapRatio;
  const barWidth = Math.max(2, (totalBarArea - totalGaps) / pts.length);
  const gap = pts.length > 1 ? (totalBarArea - barWidth * pts.length) / (pts.length - 1) : 0;

  return pts.map((point, index) => {
    const x = padding.left + ((point.t - activeDomain.value!.from) / timeSpan) * iw;
    const barHeight = ((point.value - valueRange.value.min) / valSpan) * ih;
    const y = padding.top + ih - barHeight;
    const color = getBarColor(point.value);

    return {
      ...point,
      x,
      y,
      barWidth: Math.max(1, barWidth),
      barHeight: Math.max(0, barHeight),
      color,
      gap,
    };
  });
});

// ─── Y-axis ticks ───
const yTicks = computed(() => {
  const { min, max } = valueRange.value;
  const range = max - min;
  const tickCount = 5;
  const rawStep = range / tickCount;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const niceStep = [1, 2, 2.5, 5, 10].reduce((best, n) => {
    const candidate = magnitude * n;
    return Math.abs(candidate - rawStep) < Math.abs(best - rawStep) ? candidate : best;
  }, magnitude);

  const start = Math.ceil(min / niceStep) * niceStep;
  const ticks: number[] = [];
  for (let v = start; v <= max + niceStep * 0.01; v += niceStep) {
    ticks.push(Math.round(v * 100) / 100);
  }
  return ticks;
});

const gridLines = computed(() => {
  const ih = innerHeight.value;
  const valSpan = valueRange.value.max - valueRange.value.min;
  return yTicks.value.map((tick) => ({
    value: tick,
    y: padding.top + ih - ((tick - valueRange.value.min) / valSpan) * ih,
  }));
});

// ─── Threshold lines ───
const thresholdLines = computed(() => {
  const th = props.thresholds;
  if (!th) return [];

  const lines: { value: number; label: string; color: string; y: number }[] = [];
  const ih = innerHeight.value;
  const valSpan = valueRange.value.max - valueRange.value.min;

  if (th.min !== null) {
    const y = padding.top + ih - ((th.min - valueRange.value.min) / valSpan) * ih;
    if (y >= padding.top && y <= padding.top + ih) {
      lines.push({ value: th.min, label: `MIN ${th.min.toFixed(1)}°C`, color: "#42a5f5", y });
    }
  }

  if (th.max !== null) {
    const y = padding.top + ih - ((th.max - valueRange.value.min) / valSpan) * ih;
    if (y >= padding.top && y <= padding.top + ih) {
      lines.push({ value: th.max, label: `MAX ${th.max.toFixed(1)}°C`, color: "#ef5350", y });
    }
  }

  return lines;
});

// ─── Zero line ───
const zeroLine = computed(() => {
  const { min, max } = valueRange.value;
  if (min > 0 || max < 0) return null;

  const ih = innerHeight.value;
  const valSpan = max - min;
  const y = padding.top + ih - ((0 - min) / valSpan) * ih;
  return y;
});

// ─── X-axis time labels ───
const xLabels = computed(() => {
  const pts = bars.value;
  if (pts.length === 0 || !activeDomain.value) return [];

  const timeSpan = activeDomain.value.to - activeDomain.value.from;
  const labelCount = Math.max(2, Math.min(Math.floor(innerWidth.value / 80), pts.length));
  const step = Math.max(1, Math.floor(pts.length / labelCount));

  const labels: { x: number; text: string }[] = [];
  for (let i = 0; i < pts.length; i += step) {
    const pt = pts[i];
    const text = formatTimeLabel(pt.t, timeSpan);
    labels.push({ x: pt.x + pt.barWidth / 2, text });
  }

  // Always include last point
  const last = pts[pts.length - 1];
  if (labels.length === 0 || labels[labels.length - 1].x < last.x + last.barWidth / 2 - 5) {
    labels.push({ x: last.x + last.barWidth / 2, text: formatTimeLabel(last.t, timeSpan) });
  }

  return labels;
});

function formatTimeLabel(t: number, timeSpanMs: number): string {
  const date = new Date(t);
  if (Number.isNaN(date.getTime())) return "--";

  if (timeSpanMs <= 3600000) {
    // <= 1h: HH:mm:ss
    return date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
  if (timeSpanMs <= 86400000) {
    // <= 24h: HH:mm
    return date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  }
  if (timeSpanMs <= 604800000) {
    // <= 7d: dd.MM HH:mm
    return date.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit" })
      + " " + date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  }
  // > 7d: dd.MM
  return date.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit" });
}

function formatShortTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("pl-PL", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatTooltipDate(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("pl-PL", {
    weekday: "short",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ─── Status label ───
function getStatus(value: number): string {
  const th = props.thresholds;
  if (!th) return "NORMAL";

  const { min, max } = th;

  if (min !== null && max !== null) {
    const normalRange = max - min;
    const warningZone = normalRange * 0.2;
    const warningThreshold = max - warningZone;

    if (value < min) return "LOW";
    if (value >= max) return "HIGH";
    if (value >= warningThreshold) return "WARNING";
    return "NORMAL";
  }

  if (min !== null) {
    if (value < min) return "LOW";
    return "NORMAL";
  }

  if (max !== null) {
    if (value >= max) return "HIGH";
    const warningZone = Math.abs(max) * 0.15 || 2;
    if (value >= max - warningZone) return "WARNING";
    return "NORMAL";
  }

  return "NORMAL";
}

function getStatusColor(status: string): string {
  switch (status) {
    case "LOW": return "#42a5f5";
    case "HIGH": return "#ef5350";
    case "WARNING": return "#f9a825";
    default: return "#26c6da";
  }
}

function resetZoom(): void {
  if (!fullDomain.value) return;
  viewFrom.value = fullDomain.value.from;
  viewTo.value = fullDomain.value.to;
}

function clampDomain(from: number, to: number): { from: number; to: number } | null {
  if (!fullDomain.value) return null;

  let nextFrom = from;
  let nextTo = to;
  let span = nextTo - nextFrom;

  if (span < MIN_ZOOM_SPAN_MS) {
    const center = (nextFrom + nextTo) / 2;
    nextFrom = center - MIN_ZOOM_SPAN_MS / 2;
    nextTo = center + MIN_ZOOM_SPAN_MS / 2;
    span = nextTo - nextFrom;
  }

  const fullSpan = fullDomain.value.to - fullDomain.value.from;
  if (span > fullSpan) {
    return { from: fullDomain.value.from, to: fullDomain.value.to };
  }

  if (nextFrom < fullDomain.value.from) {
    nextTo += fullDomain.value.from - nextFrom;
    nextFrom = fullDomain.value.from;
  }

  if (nextTo > fullDomain.value.to) {
    nextFrom -= nextTo - fullDomain.value.to;
    nextTo = fullDomain.value.to;
  }

  nextFrom = Math.max(fullDomain.value.from, nextFrom);
  nextTo = Math.min(fullDomain.value.to, nextTo);

  return { from: nextFrom, to: nextTo };
}

function xToTimestamp(clientX: number): number | null {
  if (!svgRef.value || !activeDomain.value) return null;
  const bounds = svgRef.value.getBoundingClientRect();
  const iw = innerWidth.value;
  if (bounds.width <= 0 || iw <= 0) return null;

  const localX = ((clientX - bounds.left) / bounds.width) * width;
  const clampedX = Math.max(padding.left, Math.min(width - padding.right, localX));
  const ratio = (clampedX - padding.left) / iw;
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

  if (clamped) {
    viewFrom.value = clamped.from;
    viewTo.value = clamped.to;
  }
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
    if (clamped) {
      viewFrom.value = clamped.from;
      viewTo.value = clamped.to;
    }
    return;
  }

  if (!bars.value.length) {
    hoverState.value = null;
    return;
  }

  // Find nearest bar
  let nearest = bars.value[0];
  let bestDistance = Math.abs(nearest.x + nearest.barWidth / 2 - localX);

  for (let i = 0; i < bars.value.length; i++) {
    const bar = bars.value[i];
    const barCenter = bar.x + bar.barWidth / 2;
    const distance = Math.abs(barCenter - localX);
    if (distance < bestDistance) {
      bestDistance = distance;
      nearest = bar;
    }
  }

  // Only show tooltip if within reasonable distance
  const maxDist = Math.max(30, nearest.barWidth * 2);
  if (bestDistance > maxDist) {
    hoverState.value = null;
    return;
  }

  hoverState.value = {
    x: nearest.x + nearest.barWidth / 2,
    y: nearest.y,
    point: {
      t: nearest.t,
      value: nearest.value,
      timestamp: nearest.timestamp,
    },
    barIndex: bars.value.indexOf(nearest),
  };

  if (localY < padding.top || localY > chartHeight.value - padding.bottom) {
    hoverState.value = null;
  }
}

function onPointerUp(event: PointerEvent): void {
  if (!isDragging.value) return;
  isDragging.value = false;
  svgRef.value?.releasePointerCapture(event.pointerId);
}

function onPointerLeave(): void {
  if (!isDragging.value) {
    hoverState.value = null;
  }
}
</script>

<template>
  <div
    ref="containerRef"
    class="rounded-xl border border-slate-800 bg-fm-panelSoft p-4"
    :class="{ 'flex-1 flex flex-col': fullscreen }"
  >
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-fm-muted">
      <div class="flex items-center gap-2">
        <span class="uppercase tracking-[0.12em]">{{ liveMode ? "Live stream" : "Historical range" }}</span>
        <span
          v-if="sensorLabel"
          class="text-fm-text"
        >{{ sensorLabel }}</span>
      </div>
      <div class="flex items-center gap-2">
        <button
          v-if="isZoomed"
          type="button"
          class="rounded-md border border-slate-600 bg-slate-900 px-3 py-1 font-semibold text-fm-text hover:border-fm-accent"
          @click="resetZoom"
        >
          Reset zoom
        </button>
        <button
          type="button"
          class="rounded-md border border-slate-600 bg-slate-900 px-2 py-1 text-fm-muted hover:border-fm-accent hover:text-fm-text"
          :title="fullscreen ? 'Exit fullscreen' : 'Fullscreen'"
          @click="emit('toggleFullscreen')"
        >
          <svg
            v-if="!fullscreen"
            xmlns="http://www.w3.org/2000/svg"
            class="h-4 w-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="15 3 21 3 21 9" />
            <polyline points="9 21 3 21 3 15" />
            <line x1="21" y1="3" x2="14" y2="10" />
            <line x1="3" y1="21" x2="10" y2="14" />
          </svg>
          <svg
            v-else
            xmlns="http://www.w3.org/2000/svg"
            class="h-4 w-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="4 14 10 14 10 20" />
            <polyline points="20 10 14 10 14 4" />
            <line x1="14" y1="10" x2="21" y2="3" />
            <line x1="3" y1="21" x2="10" y2="14" />
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
        aria-label="Sensor trend bar chart"
        preserveAspectRatio="xMidYMid meet"
        @wheel.prevent="onWheel"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @pointerleave="onPointerLeave"
      >
        <!-- Chart background -->
        <rect x="0" y="0" :width="width" :height="chartHeight" fill="#05070b" rx="4" />

        <!-- Horizontal grid lines -->
        <g>
          <line
            v-for="gl in gridLines"
            :key="'grid-' + gl.value"
            :x1="padding.left"
            :y1="gl.y"
            :x2="width - padding.right"
            :y2="gl.y"
            stroke="#1e293b"
            stroke-width="1"
            opacity="0.6"
          />
        </g>

        <!-- Y-axis labels -->
        <g class="text-[11px] fill-[#95a2b8]">
          <text
            v-for="gl in gridLines"
            :key="'ylabel-' + gl.value"
            :x="padding.left - 8"
            :y="gl.y + 4"
            text-anchor="end"
          >{{ gl.value > 0 ? '+' : '' }}{{ gl.value }}°C</text>
        </g>

        <!-- Zero reference line -->
        <line
          v-if="zeroLine !== null"
          :x1="padding.left"
          :y1="zeroLine"
          :x2="width - padding.right"
          :y2="zeroLine"
          stroke="#334155"
          stroke-width="1"
          stroke-dasharray="4,3"
          opacity="0.5"
        />

        <!-- Threshold lines -->
        <g v-for="tl in thresholdLines" :key="'thresh-' + tl.value">
          <line
            :x1="padding.left"
            :y1="tl.y"
            :x2="width - padding.right"
            :y2="tl.y"
            :stroke="tl.color"
            stroke-width="2"
            stroke-dasharray="6,3"
            opacity="0.8"
          />
          <text
            :x="width - padding.right - 6"
            :y="tl.y - 4"
            :fill="tl.color"
            font-size="10"
            font-weight="bold"
            text-anchor="end"
            opacity="0.95"
          >{{ tl.label }}</text>
        </g>

        <!-- Bars -->
        <g>
          <rect
            v-for="(bar, index) in bars"
            :key="'bar-' + bar.t + '-' + index"
            :x="bar.x"
            :y="bar.y"
            :width="Math.max(1, bar.barWidth)"
            :height="Math.max(0, bar.barHeight)"
            :fill="bar.color"
            rx="2"
            opacity="0.85"
            class="transition-opacity duration-150"
            :class="{ 'opacity-100': hoverState && hoverState.barIndex === index }"
          />
        </g>

        <!-- X-axis labels -->
        <g class="text-[10px] fill-[#95a2b8]">
          <text
            v-for="(label, i) in xLabels"
            :key="'xlabel-' + i"
            :x="label.x"
            :y="chartHeight - 8"
            text-anchor="middle"
          >{{ label.text }}</text>
        </g>

        <!-- Hover vertical line -->
        <line
          v-if="hoverState"
          :x1="hoverState.x"
          :y1="padding.top"
          :x2="hoverState.x"
          :y2="chartHeight - padding.bottom"
          stroke="#4dd0e1"
          stroke-width="1"
          opacity="0.4"
        />
      </svg>

      <!-- Tooltip -->
      <div
        v-if="hoverState"
        class="pointer-events-none absolute z-10 max-w-[280px] rounded-md border border-slate-700 bg-slate-950/95 px-3 py-2.5 text-xs shadow-panel"
        :style="{
          left: `${Math.max(8, Math.min(hoverState.x / width * 100, 78))}%`,
          top: `${Math.max(6, (hoverState.y / chartHeight * 100) - 28)}%`
        }"
      >
        <div class="flex items-center gap-2">
          <span
            class="inline-block h-2.5 w-2.5 rounded-full"
            :style="{ backgroundColor: getBarColor(hoverState.point.value) }"
          />
          <span class="font-semibold text-fm-text">
            {{ hoverState.point.value.toFixed(1) }} °C
          </span>
        </div>
        <div class="mt-1 text-fm-muted">
          {{ formatTooltipDate(hoverState.point.timestamp) }}
        </div>
        <div class="mt-0.5 text-fm-muted">
          Sensor: {{ sensorLabel || 'N/A' }}
        </div>
        <div class="mt-0.5">
          <span
            class="inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
            :style="{
              backgroundColor: getStatusColor(getStatus(hoverState.point.value)) + '22',
              color: getStatusColor(getStatus(hoverState.point.value)),
              border: '1px solid ' + getStatusColor(getStatus(hoverState.point.value)) + '44'
            }"
          >
            {{ getStatus(hoverState.point.value) }}
          </span>
        </div>
      </div>
    </div>

    <div class="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-fm-muted">
      <span>Scroll: zoom | Drag: pan</span>
      <span>{{ bars[0] ? formatShortTime(bars[0].timestamp) : "--" }}</span>
      <span>{{ bars[bars.length - 1] ? formatShortTime(bars[bars.length - 1].timestamp) : "--" }}</span>
    </div>
  </div>
</template>
