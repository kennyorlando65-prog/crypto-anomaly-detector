import { describe, expect, it } from 'vitest';
import {
  countBySeverity,
  eventsToCsv,
  filterEvents,
  formatCompact,
  formatDate,
  formatPercent,
  formatPrice,
} from '@/lib/format';
import type { AnomalyEvent } from '@/lib/types';

function event(overrides: Partial<AnomalyEvent> = {}): AnomalyEvent {
  return {
    asset_id: 'bitcoin',
    symbol: 'BTC',
    kind: 'price_zscore',
    timestamp: '2026-08-20T00:00:00+00:00',
    severity: 'notable',
    value: 100,
    baseline: 90,
    score: 3.2,
    direction: 'up',
    detail: 'test',
    ...overrides,
  };
}

describe('formatPrice', () => {
  it('uses no decimals for large values', () => {
    expect(formatPrice(82118.4)).toBe('$82,118');
  });

  it('uses two decimals for mid-range values', () => {
    expect(formatPrice(2451.85)).toBe('$2,451.85');
  });

  it('uses four decimals for small values', () => {
    expect(formatPrice(0.1234)).toBe('$0.1234');
  });

  it('returns n/a for null and non-finite input', () => {
    expect(formatPrice(null)).toBe('n/a');
    expect(formatPrice(undefined)).toBe('n/a');
    expect(formatPrice(Number.NaN)).toBe('n/a');
    expect(formatPrice(Number.POSITIVE_INFINITY)).toBe('n/a');
  });
});

describe('formatCompact', () => {
  it('abbreviates billions', () => {
    expect(formatCompact(1_545_197_000_000)).toBe('1.55T');
  });

  it('returns n/a for missing input', () => {
    expect(formatCompact(null)).toBe('n/a');
  });
});

describe('formatPercent', () => {
  it('adds a plus sign for gains', () => {
    expect(formatPercent(4.2)).toBe('+4.20%');
  });

  it('keeps the minus sign for losses', () => {
    expect(formatPercent(-3.1)).toBe('-3.10%');
  });

  it('returns n/a for missing input', () => {
    expect(formatPercent(null)).toBe('n/a');
  });
});

describe('formatDate', () => {
  it('formats an ISO timestamp as a short date', () => {
    expect(formatDate('2026-08-12T00:00:00+00:00')).toMatch(/12 Aug/);
  });

  it('returns the input unchanged when unparseable', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date');
  });
});

describe('filterEvents', () => {
  const events = [
    event({ severity: 'extreme', kind: 'price_zscore', timestamp: '2026-08-20T00:00:00+00:00' }),
    event({ severity: 'watch', kind: 'volume_spike', timestamp: '2026-08-19T00:00:00+00:00' }),
    event({ severity: 'notable', kind: 'volatility_regime', timestamp: '2026-08-18T00:00:00+00:00' }),
  ];

  it('returns everything when filters are all', () => {
    expect(filterEvents(events, { severity: 'all', kind: 'all' })).toHaveLength(3);
  });

  it('filters by severity', () => {
    const result = filterEvents(events, { severity: 'extreme' });
    expect(result).toHaveLength(1);
    expect(result[0].severity).toBe('extreme');
  });

  it('filters by detector kind', () => {
    const result = filterEvents(events, { kind: 'volume_spike' });
    expect(result).toHaveLength(1);
    expect(result[0].kind).toBe('volume_spike');
  });

  it('combines severity and kind filters', () => {
    expect(filterEvents(events, { severity: 'extreme', kind: 'volume_spike' })).toHaveLength(0);
  });

  it('sorts newest first', () => {
    const result = filterEvents(events, {});
    expect(result[0].timestamp).toBe('2026-08-20T00:00:00+00:00');
    expect(result[2].timestamp).toBe('2026-08-18T00:00:00+00:00');
  });

  it('applies a trailing day window from the newest event', () => {
    const result = filterEvents(events, { days: 1 });
    expect(result).toHaveLength(2);
  });

  it('does not mutate the input array', () => {
    const original = [...events];
    filterEvents(events, { severity: 'extreme' });
    expect(events).toEqual(original);
  });

  it('handles an empty list', () => {
    expect(filterEvents([], { severity: 'extreme', days: 30 })).toEqual([]);
  });
});

describe('countBySeverity', () => {
  it('always returns all three tiers, including zeros', () => {
    const counts = countBySeverity([event({ severity: 'extreme' })]);
    expect(counts).toEqual({ extreme: 1, notable: 0, watch: 0 });
  });

  it('counts a mixed set correctly', () => {
    const counts = countBySeverity([
      event({ severity: 'watch' }),
      event({ severity: 'watch' }),
      event({ severity: 'notable' }),
    ]);
    expect(counts).toEqual({ extreme: 0, notable: 1, watch: 2 });
  });
});

describe('eventsToCsv', () => {
  it('writes a header row', () => {
    const csv = eventsToCsv([]);
    expect(csv.split('\n')[0]).toBe(
      'asset_id,symbol,kind,timestamp,severity,value,baseline,score,direction,detail',
    );
  });

  it('writes one row per event', () => {
    const csv = eventsToCsv([event(), event({ symbol: 'ETH' })]);
    expect(csv.split('\n')).toHaveLength(3);
  });

  it('quotes fields containing a comma', () => {
    const csv = eventsToCsv([event({ detail: 'moved up, sharply' })]);
    expect(csv).toContain('"moved up, sharply"');
  });

  it('escapes embedded double quotes', () => {
    const csv = eventsToCsv([event({ detail: 'called "extreme"' })]);
    expect(csv).toContain('"called ""extreme"""');
  });
});
