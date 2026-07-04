import axios from "axios";

import type { Device, Measurement, NetworkSettings, Sensor, SystemHealth } from "@/types";

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

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

export async function fetchSystem(): Promise<SystemHealth> {
  try {
    const response = await api.get<SystemHealth>("/system");
    return response.data;
  } catch (_error) {
    const fallback = await api.get<SystemHealth>("/system/health");
    return fallback.data;
  }
}

export async function fetchSystemNetwork(): Promise<NetworkSettings> {
  const response = await api.get<NetworkSettings>("/system/network");
  return response.data;
}
