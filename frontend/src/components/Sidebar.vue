<script setup lang="ts">
const links = [
  { label: "Dashboard", to: "/" },
  { label: "Devices", to: "/devices" },
  { label: "Sensors", to: "/sensors" },
  { label: "Alarms", to: "/alarms" },
  { label: "Settings", to: "/settings" },
];
</script>

<template>
  <aside class="w-full border-r border-slate-800 bg-fm-panel/80 p-4 md:w-64 md:p-6">
    <div class="mb-8">
      <p class="text-xs font-semibold uppercase tracking-[0.2em] text-fm-accent">
        FrigoMonitor
      </p>
      <h1 class="mt-2 text-2xl font-bold text-fm-text">
        Control Center
      </h1>
    </div>

    <nav class="space-y-2">
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        class="block rounded-lg px-3 py-2 text-sm font-medium text-fm-muted transition hover:bg-fm-panelSoft hover:text-fm-text"
        active-class="bg-fm-panelSoft text-fm-text"
      >
        {{ link.label }}
      </RouterLink>
    </nav>
  </aside>
</template>
