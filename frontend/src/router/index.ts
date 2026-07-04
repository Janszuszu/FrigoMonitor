import { createRouter, createWebHistory } from "vue-router";

import MainLayout from "@/layouts/MainLayout.vue";
import AlarmsView from "@/views/AlarmsView.vue";
import DashboardView from "@/views/DashboardView.vue";
import DevicesView from "@/views/DevicesView.vue";
import SensorsView from "@/views/SensorsView.vue";
import SettingsView from "@/views/SettingsView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: MainLayout,
      children: [
        { path: "", name: "dashboard", component: DashboardView },
        { path: "devices", name: "devices", component: DevicesView },
        { path: "sensors", name: "sensors", component: SensorsView },
        { path: "alarms", name: "alarms", component: AlarmsView },
        { path: "settings", name: "settings", component: SettingsView },
      ],
    },
  ],
});

export default router;
