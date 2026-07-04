<script setup lang="ts">
import { reactive } from "vue";

import { useSystemStore } from "@/stores/system";

const systemStore = useSystemStore();

const form = reactive({
  backendUrl: systemStore.backendUrl,
  websocketUrl: systemStore.websocketUrl,
  theme: systemStore.theme,
});

function save(): void {
  systemStore.setBackendUrl(form.backendUrl.trim());
  systemStore.setWebsocketUrl(form.websocketUrl.trim());
  systemStore.setTheme(form.theme);
  console.info("Settings saved");
}
</script>

<template>
  <section class="space-y-6">
    <header>
      <h2 class="text-2xl font-semibold">
        Settings
      </h2>
      <p class="text-sm text-fm-muted">
        Connection and presentation settings.
      </p>
    </header>

    <form
      class="max-w-3xl space-y-4 rounded-xl border border-slate-800 bg-fm-panelSoft p-6"
      @submit.prevent="save"
    >
      <label class="block space-y-2 text-sm">
        <span class="font-medium text-fm-muted">Backend URL</span>
        <input
          v-model="form.backendUrl"
          class="w-full rounded-lg border border-slate-700 bg-fm-panel px-3 py-2 text-fm-text outline-none focus:border-fm-accent"
          placeholder="http://localhost:8000/api/v1"
        >
      </label>

      <label class="block space-y-2 text-sm">
        <span class="font-medium text-fm-muted">WebSocket URL</span>
        <input
          v-model="form.websocketUrl"
          class="w-full rounded-lg border border-slate-700 bg-fm-panel px-3 py-2 text-fm-text outline-none focus:border-fm-accent"
          placeholder="ws://localhost:8000/ws"
        >
      </label>

      <label class="block space-y-2 text-sm">
        <span class="font-medium text-fm-muted">Theme</span>
        <select
          v-model="form.theme"
          class="w-full rounded-lg border border-slate-700 bg-fm-panel px-3 py-2 text-fm-text outline-none focus:border-fm-accent"
        >
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
      </label>

      <button
        type="submit"
        class="rounded-lg bg-fm-accent px-4 py-2 text-sm font-semibold text-slate-900 transition hover:brightness-110"
      >
        Save settings
      </button>
    </form>
  </section>
</template>
