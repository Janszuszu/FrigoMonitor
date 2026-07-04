import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { fetchDevices } from "@/services/api";
import type { Device } from "@/types";

const ONLINE_WINDOW_MS = 5 * 60 * 1000;

export const useDevicesStore = defineStore("devices", () => {
  const items = ref<Device[]>([]);
  const loading = ref(false);

  const onlineCount = computed(() => {
    const now = Date.now();
    return items.value.filter((device) => {
      if (!device.last_seen) {
        return false;
      }
      return now - new Date(device.last_seen).getTime() < ONLINE_WINDOW_MS;
    }).length;
  });

  async function load(): Promise<void> {
    loading.value = true;
    try {
      items.value = await fetchDevices();
    } finally {
      loading.value = false;
    }
  }

  return {
    items,
    loading,
    onlineCount,
    load,
  };
});
