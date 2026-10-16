'use client';

import { useState } from 'react';
import type { Asset } from '@/lib/types';
import Dashboard from './Dashboard';
import BacktestView from './BacktestView';
import DigestView from './DigestView';
import CompareView from './CompareView';

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'digest', label: 'Digest' },
  { id: 'compare', label: 'Compare' },
] as const;

type TabId = (typeof TABS)[number]['id'];

/**
 * Tab shell.
 *
 * All four views are client components sharing one asset list, so switching
 * tabs does not refetch the market snapshot.
 */
export default function Tabs({ assets }: { assets: Asset[] }) {
  const [tab, setTab] = useState<TabId>('dashboard');

  return (
    <div className="space-y-6">
      <nav className="flex gap-1 border-b border-ink-700" aria-label="Views">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            aria-current={tab === item.id ? 'page' : undefined}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              tab === item.id
                ? 'border-signal-calm text-signal-calm'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {tab === 'dashboard' && <Dashboard assets={assets} />}
      {tab === 'backtest' && <BacktestView />}
      {tab === 'digest' && <DigestView />}
      {tab === 'compare' && <CompareView assets={assets} />}
    </div>
  );
}
