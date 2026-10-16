'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { AnomaliesResponse, Asset, SeriesResponse } from '@/lib/types';
import { fetchAnomalies, fetchSeries, exportCsvUrl } from '@/lib/api';
import { countBySeverity, filterEvents } from '@/lib/format';
import PriceChart from './PriceChart';
import EventTable from './EventTable';
import SeverityCounts from './SeverityCounts';

const DAY_OPTIONS = [30, 90, 180, 365];
const SEVERITY_OPTIONS = ['all', 'extreme', 'notable', 'watch'] as const;
const KIND_OPTIONS = [
  { value: 'all', label: 'All detectors' },
  { value: 'price_zscore', label: 'Price z-score' },
  { value: 'volume_spike', label: 'Volume spike' },
  { value: 'volatility_regime', label: 'Volatility regime' },
] as const;

interface Props {
  assets: Asset[];
}

/**
 * The main dashboard.
 *
 * One asset is charted at a time, chosen from the tracked list. Filters apply
 * to the event table and to the chart markers together, so the two views can
 * never disagree about what is being shown.
 */
export default function Dashboard({ assets }: Props) {
  const [selected, setSelected] = useState(assets[0]?.id ?? 'bitcoin');
  const [days, setDays] = useState(90);
  const [severity, setSeverity] = useState<string>('all');
  const [kind, setKind] = useState<string>('all');

  const [series, setSeries] = useState<SeriesResponse | null>(null);
  const [allEvents, setAllEvents] = useState<AnomaliesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const [seriesData, eventData] = await Promise.all([
          fetchSeries(selected, days, signal),
          fetchAnomalies({ days }, signal),
        ]);
        setSeries(seriesData);
        setAllEvents(eventData);
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [selected, days],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  // Events for the charted asset, with the active filters applied.
  const chartEvents = useMemo(() => {
    if (!series) return [];
    return filterEvents(series.events, { severity, kind });
  }, [series, severity, kind]);

  // Events across every asset, for the table.
  const tableEvents = useMemo(() => {
    if (!allEvents) return [];
    return filterEvents(allEvents.events, { severity, kind });
  }, [allEvents, severity, kind]);

  const counts = useMemo(() => countBySeverity(tableEvents), [tableEvents]);

  return (
    <div className="space-y-6">
      <section className="card p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label htmlFor="asset" className="label mb-1 block">
              Asset
            </label>
            <select
              id="asset"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
              className="rounded-md border border-ink-600 bg-ink-800 px-3 py-1.5 text-sm text-slate-200"
            >
              {assets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.symbol} - {asset.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <span className="label mb-1 block">Window</span>
            <div className="flex gap-1">
              {DAY_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setDays(option)}
                  className={`btn ${days === option ? 'btn-active' : ''}`}
                >
                  {option}d
                </button>
              ))}
            </div>
          </div>

          <div>
            <span className="label mb-1 block">Severity</span>
            <div className="flex gap-1">
              {SEVERITY_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setSeverity(option)}
                  className={`btn capitalize ${severity === option ? 'btn-active' : ''}`}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="kind" className="label mb-1 block">
              Detector
            </label>
            <select
              id="kind"
              value={kind}
              onChange={(event) => setKind(event.target.value)}
              className="rounded-md border border-ink-600 bg-ink-800 px-3 py-1.5 text-sm text-slate-200"
            >
              {KIND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="ml-auto">
            <a
              href={exportCsvUrl({ days, severity: severity === 'all' ? undefined : severity })}
              className="btn inline-block"
              download
            >
              Export CSV
            </a>
          </div>
        </div>
      </section>

      {error && (
        <div className="rounded-md border border-signal-extreme/40 bg-signal-extreme/10 px-4 py-3 text-sm text-signal-extreme">
          {error}
        </div>
      )}

      <section className="card p-4">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-slate-200">
            {series ? `${series.asset.symbol} price with flagged anomalies` : 'Loading'}
          </h2>
          <span className="text-xs text-slate-500">
            {chartEvents.length} marker{chartEvents.length === 1 ? '' : 's'} shown
          </span>
        </div>
        {loading && !series ? (
          <div className="flex h-64 items-center justify-center text-sm text-slate-500">
            Loading market data from CoinGecko.
          </div>
        ) : series ? (
          <PriceChart series={series.series} events={chartEvents} symbol={series.asset.symbol} />
        ) : null}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-200">
          Flagged events across all tracked assets
        </h2>
        <SeverityCounts counts={counts} />
        <div className="card overflow-hidden">
          <EventTable events={tableEvents} />
        </div>
      </section>
    </div>
  );
}
