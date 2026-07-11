<script setup lang="ts">
import { ref } from "vue";
import type { Sensor } from "@/types";
import { updateSensor } from "@/services/api";
import { useSensorsStore } from "@/stores/sensors";

const props = defineProps<{
  sensors: Array<Sensor & { deviceName: string }>;
}>();

const sensorsStore = useSensorsStore();

const editingId = ref<number | null>(null);
const editValue = ref("");
const savingId = ref<number | null>(null);
const errorMsg = ref<string | null>(null);

function startEdit(sensor: Sensor & { deviceName: string }): void {
  editingId.value = sensor.id;
  editValue.value = sensor.name;
  errorMsg.value = null;
}

function cancelEdit(): void {
  editingId.value = null;
  editValue.value = "";
  errorMsg.value = null;
}

async function saveEdit(sensorId: number): Promise<void> {
  const trimmed = editValue.value.trim();
  if (!trimmed) {
    errorMsg.value = "Name cannot be empty.";
    return;
  }
  if (trimmed.length > 100) {
    errorMsg.value = "Name must be 100 characters or fewer.";
    return;
  }

  savingId.value = sensorId;
  errorMsg.value = null;
  try {
    const updated = await updateSensor(sensorId, { name: trimmed });
    sensorsStore.patchById(sensorId, { name: updated.name });
    editingId.value = null;
  } catch (err) {
    errorMsg.value =
      err instanceof Error ? err.message : "Failed to save sensor name.";
  } finally {
    savingId.value = null;
  }
}

function onKeydown(e: KeyboardEvent, sensorId: number): void {
  if (e.key === "Enter") {
    e.preventDefault();
    saveEdit(sensorId);
  } else if (e.key === "Escape") {
    e.preventDefault();
    cancelEdit();
  }
}

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
            <div v-if="editingId === sensor.id" class="flex items-center gap-2">
              <input
                v-model="editValue"
                type="text"
                :disabled="savingId === sensor.id"
                class="w-48 rounded border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-fm-text outline-none focus:border-fm-accent"
                @keydown="onKeydown($event, sensor.id)"
                @blur="saveEdit(sensor.id)"
              >
              <button
                class="rounded px-2 py-1 text-xs text-green-400 hover:text-green-300 disabled:opacity-50"
                :disabled="savingId === sensor.id"
                @mousedown.prevent="saveEdit(sensor.id)"
              >
                Save
              </button>
              <button
                class="rounded px-2 py-1 text-xs text-fm-muted hover:text-fm-text"
                :disabled="savingId === sensor.id"
                @mousedown.prevent="cancelEdit"
              >
                Cancel
              </button>
              <span
                v-if="savingId === sensor.id"
                class="text-xs text-fm-muted"
              >Saving...</span>
            </div>
            <div v-else class="group flex items-center gap-2">
              <span>{{ sensor.name }}</span>
              <button
                class="inline-flex items-center justify-center rounded p-1 text-fm-muted opacity-0 transition-opacity hover:text-fm-accent group-hover:opacity-100"
                title="Rename sensor"
                @click="startEdit(sensor)"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="h-3.5 w-3.5"
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
            <p
              v-if="errorMsg && editingId === sensor.id"
              class="mt-1 text-xs text-red-400"
            >
              {{ errorMsg }}
            </p>
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
