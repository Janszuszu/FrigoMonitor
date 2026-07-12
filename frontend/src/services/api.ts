import axios from "axios";

import type { AlarmSettings, ActiveAlarm, AlarmHistoryItem, Device, Measurement, NetworkSettings, Sensor, SystemHealth, TelegramSettings, TelegramSettingsUpdate, TelegramTestResult, DeviceOfflineSettings } from "@/types";

export interface MeasurementHistoryParams {
  sensorId?: number;
  from?: string;
  to?: string;
  limit?: number;
  targetPoints?: number;
}

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

const storageKey = "fm_backend_url";

export const api = axios.create({
  baseURL: localStorage.getItem(storageKey) || DEFAULT_API_BASE,
  timeout: 10000,
});

export function setApiBaseUrl(url: string): void {
  api.defaults.baseURL = url;
  localStorage.setItem(storageKey, url);
}

export function getApiBaseUrl(): string {
  return api.defaults.baseURL || DEFAULT_API_BASE;
}

export async function fetchDevices(): Promise<Device[]> {
  const response = await api.get<Device[]>("/devices");
  return response.data;
}

export async function fetchSensors(): Promise<Sensor[]> {
  const response = await api.get<Sensor[]>("/sensors");
  return response.data;
}

export async function fetchMeasurements(limit = 100): Promise<Measurement[]> {
  try {
    const response = await api.get<Measurement[]>(`/measurements?limit=${limit}`);
    return response.data;
  } catch (_error) {
    const fallback = await api.get<Measurement[]>(`/measurements/latest?limit=${limit}`);
    return fallback.data;
  }
}

export async function fetchMeasurementHistory(params: MeasurementHistoryParams): Promise<Measurement[]> {
  const search = new URLSearchParams();

  if (params.sensorId !== undefined) {
    search.set("sensor_id", String(params.sensorId));
  }
  if (params.from) {
    search.set("from", params.from);
  }
  if (params.to) {
    search.set("to", params.to);
  }
  if (params.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  if (params.targetPoints !== undefined) {
    search.set("target_points", String(params.targetPoints));
  }

  const response = await api.get<Measurement[]>(`/measurements/history?${search.toString()}`);
  return response.data;
}

export async function fetchSystem(): Promise<SystemHealth> {
  try {
    const response = await api.get<SystemHealth>("/system");
    return response.data;
  } catch (_error) {
    const fallback = await api.get<SystemHealth>("/system/health");
    return fallback.data;
  }
}

export async function updateSensor(sensorId: number, data: Partial<Sensor>): Promise<Sensor> {
  const response = await api.put<Sensor>(`/sensors/${sensorId}`, data);
  return response.data;
}

export async function updateDeviceName(deviceId: number, displayName: string): Promise<Device> {
  const response = await api.put<Device>(`/devices/${deviceId}`, { display_name: displayName });
  return response.data;
}

export async function fetchSystemNetwork(): Promise<NetworkSettings> {
  const response = await api.get<NetworkSettings>("/system/network");
  return response.data;
}

export async function fetchAlarmSettings(): Promise<AlarmSettings[]> {
  const response = await api.get<AlarmSettings[]>("/alarms/settings");
  return response.data;
}

export async function updateAlarmSettings(sensorId: number, data: Partial<AlarmSettings>): Promise<AlarmSettings> {
  const response = await api.put<AlarmSettings>(`/alarms/settings/${sensorId}`, data);
  return response.data;
}

export async function updateAllAlarmSettings(data: Partial<AlarmSettings>[]): Promise<AlarmSettings[]> {
  const response = await api.put<AlarmSettings[]>("/alarms/settings", data);
  return response.data;
}

export async function fetchActiveAlarms(): Promise<ActiveAlarm[]> {
  const response = await api.get<ActiveAlarm[]>("/alarms/active");
  return response.data;
}

export async function fetchAlarmHistory(sensorId?: number, limit = 100): Promise<AlarmHistoryItem[]> {
  const params = new URLSearchParams();
  if (sensorId !== undefined) {
    params.set("sensor_id", String(sensorId));
  }
  params.set("limit", String(limit));
  const response = await api.get<AlarmHistoryItem[]>(`/alarms/history?${params.toString()}`);
  return response.data;
}

export async function resetAlarm(alarmId: number): Promise<{ success: boolean; message: string }> {
  const response = await api.post<{ success: boolean; message: string }>(`/alarms/${alarmId}/reset`);
  return response.data;
}

export async function resetAllAlarms(): Promise<{ success: boolean; message: string; count: number }> {
  const response = await api.post<{ success: boolean; message: string; count: number }>("/alarms/reset-all");
  return response.data;
}

export async function fetchTelegramSettings(): Promise<TelegramSettings> {
  const response = await api.get<TelegramSettings>("/telegram/settings");
  return response.data;
}

export async function updateTelegramSettings(data: TelegramSettingsUpdate): Promise<TelegramSettings> {
  const response = await api.put<TelegramSettings>("/telegram/settings", data);
  return response.data;
}

export async function testTelegramNotification(data: TelegramSettingsUpdate): Promise<TelegramTestResult> {
  const response = await api.post<TelegramTestResult>("/telegram/test", data);
  return response.data;
}

export async function fetchDeviceOfflineSettings(): Promise<DeviceOfflineSettings> {
  const response = await api.get<DeviceOfflineSettings>("/device-offline/settings");
  return response.data;
}

export async function updateDeviceOfflineSettings(data: DeviceOfflineSettings): Promise<DeviceOfflineSettings> {
  const response = await api.put<DeviceOfflineSettings>("/device-offline/settings", data);
  return response.data;
}


