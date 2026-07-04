<script setup lang="ts">
import type { Device } from "@/types";

defineProps<{
  devices: Device[];
  onlineDeviceIds: Set<number>;
}>();

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
            Name
          </th>
          <th class="px-4 py-3">
            Status
          </th>
          <th class="px-4 py-3">
            IP
          </th>
          <th class="px-4 py-3">
            Firmware
          </th>
          <th class="px-4 py-3">
            Last Seen
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="device in devices"
          :key="device.id"
          class="border-b border-slate-900/70 last:border-b-0"
        >
          <td class="px-4 py-3 text-fm-text">
            {{ device.name }}
          </td>
          <td class="px-4 py-3">
            <span
              class="rounded-full px-2 py-1 text-xs font-semibold"
              :class="onlineDeviceIds.has(device.id) ? 'bg-fm-success/20 text-fm-success' : 'bg-fm-danger/20 text-fm-danger'"
            >
              {{ onlineDeviceIds.has(device.id) ? "Online" : "Offline" }}
            </span>
          </td>
          <td class="px-4 py-3 text-fm-muted">
            {{ device.ip || "-" }}
          </td>
          <td class="px-4 py-3 text-fm-muted">
            {{ device.firmware || "-" }}
          </td>
          <td class="px-4 py-3 text-fm-muted">
            {{ formatTime(device.last_seen) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
