<script setup lang="ts">
import { ref } from "vue";

import type { Device } from "@/types";
import { useDevicesStore } from "@/stores/devices";

defineProps<{
  devices: Device[];
  onlineDeviceIds: Set<number>;
}>();

const devicesStore = useDevicesStore();

const editingId = ref<number | null>(null);
const editValue = ref("");

function startEdit(device: Device): void {
  editingId.value = device.id;
  editValue.value = device.display_name || device.name;
}

function cancelEdit(): void {
  editingId.value = null;
  editValue.value = "";
}

async function saveEdit(deviceId: number): Promise<void> {
  const trimmed = editValue.value.trim();
  if (!trimmed) {
    return;
  }
  try {
    await devicesStore.updateName(deviceId, trimmed);
  } catch (error) {
    console.error("Failed to update device name", error);
  } finally {
    editingId.value = null;
    editValue.value = "";
  }
}

function onKeydown(event: KeyboardEvent, deviceId: number): void {
  if (event.key === "Enter") {
    saveEdit(deviceId);
  } else if (event.key === "Escape") {
    cancelEdit();
  }
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
            <div v-if="editingId === device.id" class="flex items-center gap-2">
              <input
                v-model="editValue"
                type="text"
                class="w-48 rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-fm-text outline-none focus:border-fm-accent"
                maxlength="100"
                autofocus
                @keydown="onKeydown($event, device.id)"
                @blur="saveEdit(device.id)"
              />
              <button
                class="rounded px-2 py-1 text-xs font-semibold text-fm-success hover:text-green-400"
                title="Save"
                @mousedown.prevent="saveEdit(device.id)"
              >
                Save
              </button>
              <button
                class="rounded px-2 py-1 text-xs font-semibold text-fm-muted hover:text-fm-text"
                title="Cancel"
                @mousedown.prevent="cancelEdit"
              >
                Cancel
              </button>
            </div>
            <div v-else class="flex items-center gap-2">
              <span>{{ device.display_name || device.name }}</span>
              <button
                class="text-fm-muted hover:text-fm-accent"
                title="Edit name"
                @click="startEdit(device)"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                  />
                </svg>
              </button>
            </div>
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
