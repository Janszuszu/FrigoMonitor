<script setup lang="ts">
import { onMounted } from "vue";
import { useSystemStore } from "@/stores/system";

const systemStore = useSystemStore();

onMounted(() => {
  systemStore.applyTheme();
});
</script>

<template>
  <RouterView />
</template>
