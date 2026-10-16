'use client';

import { useCallback, useEffect, useState } from 'react';
import type { Asset, CompareResponse } from '@/lib/types';
import { fetchCompare } from '@/lib/api';
import PriceChart from './PriceChart';
import EventTable from './EventTable';

const DAY_OPTIONS = [30, 90, 180, 365];

/**
 * Compare two assets side by side.
 *
 * Each asset keeps its own y-axis. Sharing one axis would make a cheap asset
 * look flat next to an expensive one, which is a visual lie about the shape
 * of the series.
 */
export default function CompareView({ assets }: { assets: Asset[] }) {
  const [a, setA] = useState(assets[0]?.id ?? 'bitcoin');
  const [b, setB] = useState(assets[1]?.id ?? 'ethereum');
  const [days, setDays] = useState(90);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        setData(await fetchCompare(a, b, days, signal));
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [a, b, days],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const selectClass =
    'rounded-md border border-ink-600 bg-ink-800 px-3 py-1.5 text-sm text-slate-200';

  return (
    <div className="space-y-6">
      <section className="card p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label htmlFor="asset-a" className="label mb-1 block">
              Asset A
            </label>
            <select id="asset-a" value={a} onChange={(e) => setA(e.target.value)} className={selectClass}>
              {assets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.symbol} - {asset.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="asset-b" className="label mb-1 block">
              Asset B
            </label>
            <select id="asset-b" value={b} onChange={(e) => setB(e.target.value)} className={selectClass}>
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
        </div>
      </section>

      {error && (
        <div className="rounded-md border border-signal-extreme/40 bg-signal-extreme/10 px-4 py-3 text-sm text-signal-extreme">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="card flex h-40 items-center justify-center text-sm text-slate-500">
          Loading both series.
        </div>
      ) : data ? (
        <div className="grid gap-6 lg:grid-cols-2">
          {([data.a, data.b] as const).map((side) => (
            <section key={side.asset.id} className="space-y-3">
              <div className="card p-4">
                <div className="mb-3 flex items-baseline justify-between">
                  <h3 className="text-sm font-semibold text-slate-200">
                    {side.asset.symbol} - {side.asset.name}
                  </h3>
                  <span className="text-xs text-slate-500">
                    {side.summary.total} flag{side.summary.total === 1 ? '' : 's'}
                  </span>
                </div>
                <PriceChart series={side.series} events={side.events} symbol={side.asset.symbol} height={200} />
              </div>
              <div className="card overflow-hidden">
                <EventTable events={side.events} showAsset={false} />
              </div>
            </section>
          ))}
        </div>
      ) : null}
    </div>
  );
}
