export interface Device {
  id: number;
  name: string;
  serial_number: string | null;
  location: string | null;
  created_at: string | null;
  last_seen: string | null;
  firmware?: string | null;
  ip?: string | null;
}

export interface Sensor {
  id: number;
  device_id: number;
  name: string;
  sensor_type?: string | null;
  address?: string | null;
  correction?: number | null;
  alarm_state: string;
  alarm_level?: string | null;
  last_value?: number | null;
  last_measurement?: string | null;
  unit?: string | null;
}

export interface Measurement {
  id: number;
  sensor_id: number;
  measured_at: string;
  value: number;
  unit?: string | null;
  created_at?: string | null;
}

export interface AlarmRow {
  id: string;
  severity: string;
  device: string;
  sensor: string;
  message: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface SystemHealth {
  status: string;
  app?: string;
}

export interface NetworkSettings {
  mqtt_host: string;
  mqtt_port: number;
  mqtt_user: string;
  mqtt_password_configured: boolean;
  frontend_origins: string[];
}

export interface LiveEvent {
  event?: string;
  timestamp?: string;
  payload?: Record<string, unknown>;
}
