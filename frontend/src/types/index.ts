export interface Device {
  id: number;
  name: string;
  display_name?: string | null;
  serial_number: string | null;
  device_id?: string | null;
  location: string | null;
  created_at: string | null;
  last_seen: string | null;
  firmware?: string | null;
  ip?: string | null;
  status?: string | null;
}

export interface Sensor {
  id: number;
  device_id: number;
  name: string;
  sensor_id?: string | null;
  sensor_type?: string | null;
  address?: string | null;
  rom?: string | null;
  correction?: number | null;
  alarm_state: string;
  alarm_level?: string | null;
  alarm_no_data_enabled: boolean;
  alarm_no_data_timeout: number;
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
  name?: string;
  version?: string;
  app?: string;
}

export interface NetworkSettings {
  mqtt_host: string;
  mqtt_port: number;
  mqtt_user: string;
  mqtt_password_configured: boolean;
  frontend_origins: string[];
}

export interface AlarmSettings {
  sensor_id: number;
  device_id: number;
  sensor_name: string;
  device_name: string;
  device_display_name: string | null;
  current_temperature: number | null;
  alarm_enabled: boolean;
  alarm_low: number | null;
  alarm_high: number | null;
  alarm_activation_delay: number;
  alarm_state: string;
  alarm_level: string | null;
  alarm_no_data_enabled: boolean;
  alarm_no_data_timeout: number;
}

export interface ActiveAlarm {
  id: number;
  sensor_id: number;
  device_id: number | null;
  alarm_type: string;
  threshold: number | null;
  temperature: number | null;
  state: string;
  pending_start: string | null;
  activated_at: string | null;
  cleared_at: string | null;
  created_at: string | null;
  sensor_name: string;
  device_name: string;
  device_display_name: string | null;
}

export interface AlarmHistoryItem {
  id: number;
  sensor_id: number;
  device_id: number | null;
  alarm_type: string;
  threshold: number | null;
  temperature: number | null;
  state: string;
  pending_start: string | null;
  activated_at: string | null;
  cleared_at: string | null;
  created_at: string | null;
  sensor_name: string;
  device_name: string;
  device_display_name: string | null;
}

export interface LiveEvent {
  event?: string;
  timestamp?: string;
  payload?: Record<string, unknown> | null;
}

export interface TelegramSettings {
  enabled: boolean;
  chat_id: string;
  bot_token_configured: boolean;
}

export interface TelegramSettingsUpdate {
  enabled: boolean;
  bot_token: string;
  chat_id: string;
}

export interface TelegramTestResult {
  success: boolean;
  message: string;
}

export interface DeviceOfflineAlarmSettings {
  enabled: boolean;
  offline_timeout_minutes: number;
  severity: string;
  notifications_enabled: boolean;
}

export interface DeviceOfflineAlarmSettingsUpdate {
  enabled: boolean;
  offline_timeout_minutes: number;
  severity: string;
  notifications_enabled: boolean;
}

