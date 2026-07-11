<script setup lang="ts">
import { onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";

const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();

const router = useRouter();

const links = [
  { label: "Dashboard", to: "/" },
  { label: "Devices", to: "/devices" },
  { label: "Sensors", to: "/sensors" },
  { label: "Alarms", to: "/alarms" },
  { label: "Settings", to: "/settings" },
];

function onBackdropClick(): void {
  emit("close");
}

function onNavClick(): void {
  emit("close");
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && props.open) {
    emit("close");
  }
}

onMounted(() => {
  document.addEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <Transition name="drawer-backdrop">
      <div
        v-if="open"
        class="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        aria-hidden="true"
        @click="onBackdropClick"
      />
    </Transition>

    <!-- Drawer -->
    <Transition name="drawer-slide">
      <aside
        v-if="open"
        class="fixed left-0 top-0 z-50 flex h-full w-64 flex-col border-r border-slate-800 bg-fm-panel shadow-panel"
        role="navigation"
        aria-label="Main navigation"
      >
        <div class="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <span class="text-xs font-semibold uppercase tracking-[0.2em] text-fm-accent">
            FrigoMonitor
          </span>
          <button
            type="button"
            class="flex h-8 w-8 items-center justify-center rounded-md text-fm-muted transition hover:bg-fm-panelSoft hover:text-fm-text focus:outline-none focus-visible:ring-2 focus-visible:ring-fm-accent"
            aria-label="Close navigation menu"
            @click="emit('close')"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <nav class="flex-1 space-y-1 px-3 py-4">
          <RouterLink
            v-for="link in links"
            :key="link.to"
            :to="link.to"
            class="flex items-center rounded-lg px-4 py-2.5 text-sm font-medium text-fm-muted transition hover:bg-fm-panelSoft hover:text-fm-text focus:outline-none focus-visible:ring-2 focus-visible:ring-fm-accent"
            active-class="bg-fm-panelSoft text-fm-text"
            @click="onNavClick"
          >
            {{ link.label }}
          </RouterLink>
        </nav>

        <div class="border-t border-slate-800 px-5 py-3">
          <p class="text-[10px] uppercase tracking-[0.15em] text-fm-muted/50">
            FrigoMonitor v1
          </p>
        </div>
      </aside>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-backdrop-enter-active,
.drawer-backdrop-leave-active {
  transition: opacity 0.2s ease;
}
.drawer-backdrop-enter-from,
.drawer-backdrop-leave-to {
  opacity: 0;
}

.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(-100%);
}
</style>
