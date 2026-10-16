'use client';

import { useCallback, useEffect, useState } from 'react';
import type { BacktestResponse } from '@/lib/types';
import { fetchBacktest } from '@/lib/api';
import EventTable from './EventTable';

const DAY_OPTIONS = [30, 90, 180, 365];

/**
 * Backtest view.
 *
 * This is the credibility feature. It answers "if you had been watching this
 * for 90 days, how many alerts would have fired?" and reports the answer
 * plainly, including when the answer is "a lot".
 *
 * It deliberately does not report accuracy, precision, or profit. The
 * detectors make no prediction, so any such number would be invented.
 */
export default function BacktestView() {
  const [days, setDays] = useState(90);
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async (signal: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchBacktest(days, undefined, signal));
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const expandedAsset = data?.assets.find((asset) => asset.asset_id === expanded);

  return (
    <div className="space-y-6">
      <section className="card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <span className="label mb-1 block">Replay window</span>
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
          {data && (
            <div className="ml-auto flex gap-6">
              <div>
                <div className="label">Total flags</div>
                <div className="font-mono text-2xl font-semibold text-slate-100">
                  {data.totals.events}
                </div>
              </div>
              <div>
                <div className="label">Per week</div>
                <div className="font-mono text-2xl font-semibold text-signal-calm">
                  {data.totals.events_per_week}
                </div>
              </div>
              <div>
                <div className="label">Assets</div>
                <div className="font-mono text-2xl font-semibold text-slate-100">
                  {data.totals.assets}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      <div className="rounded-md border border-signal-watch/30 bg-signal-watch/5 px-4 py-3 text-sm text-slate-300">
        <strong className="font-semibold text-signal-watch">What this measures.</strong>{' '}
        {data?.note ??
          'Counts of statistical flags over a historical window. This is a false-positive load measurement, not a performance or accuracy claim.'}
      </div>

      {error && (
        <div className="rounded-md border border-signal-extreme/40 bg-signal-extreme/10 px-4 py-3 text-sm text-signal-extreme">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="card flex h-40 items-center justify-center text-sm text-slate-500">
          Replaying the detectors over {days} days of history.
        </div>
      ) : data ? (
        <section className="card overflow-hidden">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-ink-700 text-left">
                <th className="label px-3 py-2">Asset</th>
                <th className="label px-3 py-2 text-right">Days</th>
                <th className="label px-3 py-2 text-right">Flags</th>
                <th className="label px-3 py-2 text-right">Per week</th>
                <th className="label px-3 py-2 text-right">Extreme</th>
                <th className="label px-3 py-2 text-right">Notable</th>
                <th className="label px-3 py-2 text-right">Watch</th>
                <th className="label px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {data.assets.map((asset) => (
                <tr key={asset.asset_id} className="border-b border-ink-800/60">
                  <td className="px-3 py-2 font-medium text-slate-200">{asset.symbol}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-slate-400">
                    {asset.days}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-slate-100">
                    {asset.total_events}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-signal-calm">
                    {asset.events_per_week}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-signal-extreme">
                    {asset.by_severity.extreme}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-signal-notable">
                    {asset.by_severity.notable}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-signal-watch">
                    {asset.by_severity.watch}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() =>
                        setExpanded(expanded === asset.asset_id ? null : asset.asset_id)
                      }
                      className="btn text-xs"
                    >
                      {expanded === asset.asset_id ? 'Hide' : 'Events'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {expandedAsset && (
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-slate-200">
            {expandedAsset.symbol} - every flag in the window
          </h3>
          <div className="card overflow-hidden">
            <EventTable events={expandedAsset.events} showAsset={false} />
          </div>
        </section>
      )}
    </div>
  );
}
