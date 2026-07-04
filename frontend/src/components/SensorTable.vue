<script setup lang="ts">
import type { Sensor } from "@/types";

defineProps<{
  sensors: Array<Sensor & { deviceName: string }>;
}>();

function formatTemperature(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(1)} C`;
}

function formatTime(value: string | null | undefined): string {
  if (!value) {
    return "No data";
  }
  return new Date(value).toLocaleString();
}
</script>

<template>
  <div class="overflow-x-auto rounded-xl border border-slate-800 bg-fm-panelSoft">
    <table class="min-w-full text-left text-sm">
      <thead class="border-b border-slate-800 text-xs uppercase tracking-wide text-fm-muted">
        <tr>
          <th class="px-4 py-3">
            Device
          </th>
          <th class="px-4 py-3">
            Sensor
          </th>
          <th class="px-4 py-3">
            Temperature
          </th>
          <th class="px-4 py-3">
            Status
          </th>
          <th class="px-4 py-3">
            Last Update
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="sensor in sensors"
          :key="sensor.id"
          class="border-b border-slate-900/70 last:border-b-0"
        >
          <td class="px-4 py-3 text-fm-text">
            {{ sensor.deviceName }}
          </td>
          <td class="px-4 py-3 text-fm-text">
            {{ sensor.name }}
          </td>
          <td class="px-4 py-3 text-fm-accent">
            {{ formatTemperature(sensor.last_value) }}
          </td>
          <td class="px-4 py-3 text-fm-muted">
            {{ sensor.alarm_state || "NORMAL" }}
          </td>
          <td class="px-4 py-3 text-fm-muted">
            {{ formatTime(sensor.last_measurement) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
