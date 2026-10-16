export default function Home() {
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
          <strong className="font-semibold text-slate-300">
            This is statistical anomaly detection, not machine learning.
          </strong>{' '}
          There is no trained model and no prediction of future prices. A flag means an
          observation is unusual for that asset, nothing more. Not investment advice.
        </p>
      </header>

      <AppShell />

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
