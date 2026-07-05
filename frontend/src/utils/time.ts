const TZ_SUFFIX_RE = /(Z|[+-]\d{2}:\d{2})$/i;

export function parseApiTimestampMillis(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }

  // Backend can return naive ISO datetimes (without timezone); treat them as UTC.
  const normalized = TZ_SUFFIX_RE.test(value) ? value : `${value}Z`;
  const ms = Date.parse(normalized);
  return Number.isNaN(ms) ? null : ms;
}