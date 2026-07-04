import { ref } from "vue";
import { defineStore } from "pinia";

import { fetchSensors } from "@/services/api";
import type { Sensor } from "@/types";

export const useSensorsStore = defineStore("sensors", () => {
  const items = ref<Sensor[]>([]);
  const loading = ref(false);

  async function load(): Promise<void> {
    loading.value = true;
    try {
      items.value = await fetchSensors();
    } finally {
      loading.value = false;
    }
  }

  return {
    items,
    loading,
    load,
  };
});
