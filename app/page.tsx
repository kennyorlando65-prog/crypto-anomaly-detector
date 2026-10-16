import type { Asset } from '@/lib/types';
import { API_BASE } from '@/lib/api';
import Tabs from '@/components/Tabs';

/**
 * Server component.
 *
 * The asset list is fetched on the server so the first paint already has the
 * tracked assets and the tab shell can render without a client-side waterfall.
 * If the backend is unreachable the page still renders, with a clear notice
 * rather than a blank screen.
 */
async function loadAssets(): Promise<{ assets: Asset[]; error: string | null }> {
  try {
    const response = await fetch(`${API_BASE}/assets`, { cache: 'no-store' });
    if (!response.ok) {
      return { assets: [], error: `The detection engine returned HTTP ${response.status}.` };
    }
    const payload = (await response.json()) as { assets: Asset[] };
    return { assets: payload.assets ?? [], error: null };
  } catch (err) {
    return {
      assets: [],
      error: `Could not reach the detection engine at ${API_BASE}. ${(err as Error).message}`,
    };
  }
}

export default async function Home() {
  const { assets, error } = await loadAssets();

  return (
    <main className="mx-auto max-w-6xl px-5 py-10">
      <header className="mb-8">
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-100">
            Crypto Open-Data Anomaly Detector
          </h1>
          <span className="chip border-signal-calm/40 bg-signal-calm/10 text-signal-calm">
            v1.1
          </span>
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
          Rolling z-scores, volume spikes and volatility regime changes over CoinGecko public
          market data. Every baseline is computed from data strictly before the point being
          scored, so nothing is measured against its own future.
        </p>
        <p className="mt-3 max-w-3xl rounded-md border border-ink-700 bg-ink-900/60 px-3 py-2 text-xs leading-relaxed text-slate-400">
          <strong className="font-semibold text-slate-300">This is statistical anomaly detection, not machine learning.</strong>{' '}
          There is no trained model and no prediction of future prices. A flag means an
          observation is unusual for that asset, nothing more. Not investment advice.
        </p>
      </header>

      {error ? (
        <div className="rounded-md border border-signal-extreme/40 bg-signal-extreme/10 px-4 py-4 text-sm text-signal-extreme">
          <p className="font-semibold">The dashboard could not load its asset list.</p>
          <p className="mt-1 text-signal-extreme/80">{error}</p>
          <p className="mt-2 text-xs text-slate-400">
            Locally, start the engine with{' '}
            <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono">
              uvicorn api.index:app --reload --port 8000
            </code>{' '}
            and set{' '}
            <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono">
              NEXT_PUBLIC_API_BASE=http://localhost:8000
            </code>
            .
          </p>
        </div>
      ) : (
        <Tabs assets={assets} />
      )}

      <footer className="mt-12 border-t border-ink-800 pt-5 text-xs leading-relaxed text-slate-500">
        <p>
          Data from the CoinGecko public API. Detection is classical statistics: rolling
          z-scores, volume ratios and realised-volatility ratios. No machine learning, no
          price prediction, no investment advice.
        </p>
      </footer>
    </main>
  );
}
