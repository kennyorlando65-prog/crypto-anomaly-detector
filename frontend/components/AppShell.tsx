'use client';

import { useCallback, useEffect, useState } from 'react';
import type { Asset } from '@/lib/types';
import { ApiError, fetchAssets } from '@/lib/api';
import Tabs from './Tabs';
import EngineError from './EngineError';

/**
 * Owns the one piece of data every view needs: the tracked asset list.
 *
 * This runs in the browser on purpose. See the note in `lib/api.ts`: resolving
 * a relative API path is only possible where an origin exists, and the browser
 * is that place. The previous version fetched this from a Server Component and
 * threw "Failed to parse URL" before a request was ever made.
 */
export default function AppShell() {
  const [assets, setAssets] = useState<Asset[] | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const load = useCallback(async (signal: AbortSignal) => {
    try {
      const loaded = await fetchAssets(signal);
      setAssets(loaded);
      setFailure(null);
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      setFailure(err as ApiError);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (failure) return <EngineError failure={failure} />;

  if (!assets) {
    return (
      <div className="card p-6 text-sm text-slate-400" role="status">
        Loading tracked assets from the detection engine...
      </div>
    );
  }

  return <Tabs assets={assets} />;
}
