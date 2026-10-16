/**
 * Formatting and filtering helpers.
 *
 * Kept as pure functions with no React or DOM dependency, so they can be
 * unit tested directly. The dashboard's filter behaviour is defined here
 * rather than inside a component, which is what makes it testable.
 */

import type { AnomalyEvent, Severity } from './types';

export const SEVERITY_ORDER: Record<Severity, number> = {
  extreme: 0,
  notable: 1,
  watch: 2,
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  extreme: 'Extreme',
  notable: 'Notable',
  watch: 'Watch',
};

export const KIND_LABEL: Record<string, string> = {
  price_zscore: 'Price z-score',
  volume_spike: 'Volume spike',
  volatility_regime: 'Volatility regime',
};

/** Format a USD price with a sensible number of decimals for its magnitude. */
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'n/a';
  const abs = Math.abs(value);
  // Above 10,000 the cents are noise and only add width. Between 1 and 10,000
  // the cents are meaningful, so they are kept.
  if (abs >= 10000) return `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  if (abs >= 1) return `$${value.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
  if (abs >= 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toPrecision(4)}`;
}

/** Compact notation for large numbers, e.g. 1.5B. */
export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'n/a';
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 }).format(value);
}

/** Signed percentage, e.g. +4.2%. */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'n/a';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

/** Short date, e.g. 12 Aug. */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

/** Full date and time, for tooltips. */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Filter events by severity, detector kind and a trailing time window.
 *
 * A null or 'all' filter means "do not filter on this dimension". The time
 * window is measured from the newest event in the set rather than from the
 * wall clock, so the view stays stable when the data is historical.
 */
export function filterEvents(
  events: AnomalyEvent[],
  options: { severity?: string | null; kind?: string | null; days?: number | null },
): AnomalyEvent[] {
  let result = [...events];

  const severity = options.severity;
  if (severity && severity !== 'all') {
    result = result.filter((event) => event.severity === severity);
  }

  const kind = options.kind;
  if (kind && kind !== 'all') {
    result = result.filter((event) => event.kind === kind);
  }

  const days = options.days;
  if (days && days > 0 && result.length > 0) {
    const newest = Math.max(...result.map((event) => new Date(event.timestamp).getTime()));
    const cutoff = newest - days * 86_400_000;
    result = result.filter((event) => new Date(event.timestamp).getTime() >= cutoff);
  }

  return result.sort((a, b) => {
    const byTime = b.timestamp.localeCompare(a.timestamp);
    if (byTime !== 0) return byTime;
    return SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
  });
}

/** Count events per severity, always returning all three keys. */
export function countBySeverity(events: AnomalyEvent[]): Record<Severity, number> {
  const counts: Record<Severity, number> = { watch: 0, notable: 0, extreme: 0 };
  for (const event of events) counts[event.severity] += 1;
  return counts;
}

/**
 * Build the CSV body for a set of events.
 *
 * Mirrors the server-side export so the two can be compared in a test.
 */
export function eventsToCsv(events: AnomalyEvent[]): string {
  const header = [
    'asset_id',
    'symbol',
    'kind',
    'timestamp',
    'severity',
    'value',
    'baseline',
    'score',
    'direction',
    'detail',
  ];
  const escape = (field: string | number) => {
    const text = String(field);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const rows = events.map((event) =>
    [
      event.asset_id,
      event.symbol,
      event.kind,
      event.timestamp,
      event.severity,
      event.value,
      event.baseline,
      event.score,
      event.direction,
      event.detail,
    ]
      .map(escape)
      .join(','),
  );
  return [header.join(','), ...rows].join('\n');
}
