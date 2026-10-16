'use client';

import { useCallback, useEffect, useState } from 'react';
import type { DigestResponse } from '@/lib/types';
import { fetchDigest } from '@/lib/api';
import EventTable from './EventTable';

const HOUR_OPTIONS = [24, 72, 168];

/**
 * Alert digest view.
 *
 * A plain summary of what fired in a window, with a copy button for the text
 * form. There is no email or webhook, because those need a third-party
 * service and this project deliberately has none.
 */
export default function DigestView() {
  const [hours, setHours] = useState(24);
  const [data, setData] = useState<DigestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async (signal: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchDigest(hours, 90, signal));
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [hours]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const copy = async () => {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('Clipboard access was refused by the browser.');
    }
  };

  return (
    <div className="space-y-6">
      <section className="card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <span className="label mb-1 block">Window</span>
            <div className="flex gap-1">
              {HOUR_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setHours(option)}
                  className={`btn ${hours === option ? 'btn-active' : ''}`}
                >
                  {option === 168 ? '7d' : `${option}h`}
                </button>
              ))}
            </div>
          </div>
          <button type="button" onClick={copy} className="btn ml-auto" disabled={!data}>
            {copied ? 'Copied' : 'Copy digest text'}
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded-md border border-signal-extreme/40 bg-signal-extreme/10 px-4 py-3 text-sm text-signal-extreme">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="card flex h-40 items-center justify-center text-sm text-slate-500">
          Building the digest.
        </div>
      ) : data ? (
        <>
          <section className="grid gap-3 sm:grid-cols-4">
            {(['extreme', 'notable', 'watch'] as const).map((tier) => (
              <div key={tier} className="card px-4 py-3">
                <div className="label capitalize">{tier}</div>
                <div className="mt-1 font-mono text-2xl font-semibold text-slate-100">
                  {data.counts[tier]}
                </div>
              </div>
            ))}
            <div className="card px-4 py-3">
              <div className="label">Total</div>
              <div className="mt-1 font-mono text-2xl font-semibold text-signal-calm">
                {data.total}
              </div>
            </div>
          </section>

          <section className="card p-4">
            <h3 className="label mb-2">Digest text</h3>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-ink-700 bg-ink-950 p-4 font-mono text-xs leading-relaxed text-slate-300">
              {data.text}
            </pre>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-200">Events in this window</h3>
            <div className="card overflow-hidden">
              <EventTable
                events={data.events}
                emptyMessage={`Nothing was flagged in the last ${hours} hours.`}
              />
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
