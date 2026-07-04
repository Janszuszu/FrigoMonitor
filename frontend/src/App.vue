<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { fetchDashboardData, openLiveSocket } from "./api";

const ONLINE_WINDOW_MS = 5 * 60 * 1000;

const devices = ref([]);
const sensors = ref([]);
const measurements = ref([]);
const system = ref(null);
const loading = ref(true);
const error = ref("");
const wsStatus = ref("offline");
const events = ref([]);
let socket = null;

const sensorById = computed(() => new Map(sensors.value.map((sensor) => [sensor.id, sensor])));

const deviceCards = computed(() =>
  devices.value.map((device) => {
    const deviceSensors = sensors.value.filter((sensor) => sensor.device_id === device.id);
    const activeAlarms = deviceSensors.filter((sensor) => sensor.alarm_state && sensor.alarm_state !== "NORMAL");
    const lastMeasurement = mostRecentDate([
      device.last_seen,
      ...deviceSensors.map((sensor) => sensor.last_measurement),
    ]);

    return {
      ...device,
      sensors: deviceSensors,
      activeAlarms,
      online: isOnline(lastMeasurement),
      lastMeasurement,
    };
  }),
);

const latestTemperatures = computed(() =>
  [...sensors.value]
    .sort((left, right) => dateValue(right.last_measurement) - dateValue(left.last_measurement))
    .slice(0, 8),
);

const activeAlarms = computed(() =>
  sensors.value.filter((sensor) => sensor.alarm_state && sensor.alarm_state !== "NORMAL"),
);

const stats = computed(() => ({
  devices: devices.value.length,
  sensors: sensors.value.length,
  online: deviceCards.value.filter((device) => device.online).length,
  alarms: activeAlarms.value.length,
}));

onMounted(async () => {
  await refresh();
  connectSocket();
});

onUnmounted(() => {
  socket?.close();
});

async function refresh() {
  loading.value = true;
  error.value = "";
  try {
    const data = await fetchDashboardData();
    devices.value = data.devices;
    sensors.value = data.sensors;
    measurements.value = data.measurements;
    system.value = data.system;
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

function connectSocket() {
  socket?.close();
  wsStatus.value = "connecting";
  socket = openLiveSocket({
    onOpen: () => {
      wsStatus.value = "online";
    },
    onClose: () => {
      wsStatus.value = "offline";
    },
    onError: () => {
      wsStatus.value = "error";
    },
    onMessage: handleLiveEvent,
  });
}

function handleLiveEvent(message) {
  events.value = [message, ...events.value].slice(0, 12);
  if (message.event === "measurement.saved") {
    const payload = message.payload ?? {};
    const sensor = sensorById.value.get(payload.sensor_id);
    if (sensor) {
      sensor.last_value = payload.value;
      sensor.last_measurement = payload.timestamp ?? message.timestamp;
    }
  }
  if (message.event?.startsWith("alarm.")) {
    refresh();
  }
}

function isOnline(timestamp) {
  if (!timestamp) return false;
  return Date.now() - dateValue(timestamp) <= ONLINE_WINDOW_MS;
}

function dateValue(timestamp) {
  return timestamp ? new Date(timestamp).getTime() : 0;
}

function mostRecentDate(values) {
  const latest = values.filter(Boolean).sort((left, right) => dateValue(right) - dateValue(left))[0];
  return latest ?? null;
}

function formatTemperature(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)} C` : "--";
}

function formatTime(value) {
  if (!value) return "brak danych";
  return new Intl.DateTimeFormat("pl-PL", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    day: "2-digit",
    month: "2-digit",
  }).format(new Date(value));
}
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">
          FM-015 Web UI
        </p>
        <h1>FrigoMonitor</h1>
      </div>
      <div
        class="connection"
        :class="wsStatus"
      >
        <span />
        {{ wsStatus }}
      </div>
    </header>

    <section class="status-grid">
      <article>
        <span>Urządzenia</span>
        <strong>{{ stats.devices }}</strong>
      </article>
      <article>
        <span>Online</span>
        <strong>{{ stats.online }}</strong>
      </article>
      <article>
        <span>Sensory</span>
        <strong>{{ stats.sensors }}</strong>
      </article>
      <article class="alarm-stat">
        <span>Alarmy</span>
        <strong>{{ stats.alarms }}</strong>
      </article>
    </section>

    <div
      v-if="error"
      class="notice"
    >
      {{ error }}
      <button
        type="button"
        @click="refresh"
      >
        Ponów
      </button>
    </div>

    <section
      class="dashboard-grid"
      :class="{ muted: loading }"
    >
      <div class="panel devices-panel">
        <div class="panel-header">
          <h2>Urządzenia</h2>
          <button
            type="button"
            @click="refresh"
          >
            Odśwież
          </button>
        </div>

        <div
          v-if="deviceCards.length === 0"
          class="empty"
        >
          Brak zarejestrowanych urządzeń.
        </div>
        <article
          v-for="device in deviceCards"
          :key="device.id"
          class="device-card"
        >
          <div class="device-heading">
            <div>
              <h3>{{ device.name }}</h3>
              <p>{{ device.location || device.serial_number || `ID ${device.id}` }}</p>
            </div>
            <span
              class="pill"
              :class="{ online: device.online }"
            >
              {{ device.online ? "online" : "offline" }}
            </span>
          </div>
          <div
            v-for="sensor in device.sensors"
            :key="sensor.id"
            class="sensor-row"
          >
            <span>{{ sensor.name }}</span>
            <strong>{{ formatTemperature(sensor.last_value) }}</strong>
            <em :class="{ alarm: sensor.alarm_state !== 'NORMAL' }">{{ sensor.alarm_state }}</em>
          </div>
          <footer>Ostatni pomiar: {{ formatTime(device.lastMeasurement) }}</footer>
        </article>
      </div>

      <div class="panel">
        <div class="panel-header">
          <h2>Temperatura</h2>
          <span>{{ measurements.length }} pomiarów</span>
        </div>
        <div class="temperature-list">
          <div
            v-for="sensor in latestTemperatures"
            :key="sensor.id"
            class="temperature-item"
          >
            <div>
              <span>{{ sensor.name }}</span>
              <small>{{ formatTime(sensor.last_measurement) }}</small>
            </div>
            <strong>{{ formatTemperature(sensor.last_value) }}</strong>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <h2>Alarmy</h2>
          <span>{{ activeAlarms.length }} aktywnych</span>
        </div>
        <div
          v-if="activeAlarms.length === 0"
          class="empty"
        >
          Brak aktywnych alarmów.
        </div>
        <div
          v-for="alarm in activeAlarms"
          :key="alarm.id"
          class="alarm-item"
        >
          <strong>{{ alarm.name }}</strong>
          <span>{{ alarm.alarm_level || alarm.alarm_state }}</span>
          <small>{{ formatTime(alarm.alarm_pending_since || alarm.last_measurement) }}</small>
        </div>
      </div>

      <div class="panel events-panel">
        <div class="panel-header">
          <h2>Live</h2>
          <span>{{ system?.status || "offline" }}</span>
        </div>
        <div
          v-if="events.length === 0"
          class="empty"
        >
          Oczekiwanie na zdarzenia WebSocket.
        </div>
        <div
          v-for="event in events"
          :key="`${event.event}-${event.timestamp}`"
          class="event-item"
        >
          <strong>{{ event.event }}</strong>
          <small>{{ formatTime(event.timestamp) }}</small>
        </div>
      </div>
    </section>
  </main>
</template>
