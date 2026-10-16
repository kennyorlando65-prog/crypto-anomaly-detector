import type { AnomalyEvent } from '@/lib/types';
import { KIND_LABEL, formatDateTime, formatPrice } from '@/lib/format';
import SeverityBadge from './SeverityBadge';

interface Props {
  events: AnomalyEvent[];
  showAsset?: boolean;
  emptyMessage?: string;
}

/**
 * Table of flagged events.
 *
 * The score column is labelled per detector rather than uniformly, because a
 * z-score and a volume ratio are not the same unit and presenting them as one
 * column of "score" would invite a false comparison.
 */
export default function EventTable({ events, showAsset = true, emptyMessage }: Props) {
  if (events.length === 0) {
    return (
      <div className="rounded-md border border-ink-700 bg-ink-850 px-4 py-8 text-center text-sm text-slate-500">
        {emptyMessage ?? 'No anomalies match the current filters.'}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-ink-700 text-left">
            <th className="label px-3 py-2">Date</th>
            {showAsset && <th className="label px-3 py-2">Asset</th>}
            <th className="label px-3 py-2">Detector</th>
            <th className="label px-3 py-2">Severity</th>
            <th className="label px-3 py-2 text-right">Observed</th>
            <th className="label px-3 py-2 text-right">Baseline</th>
            <th className="label px-3 py-2 text-right">Score</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr
              key={`${event.asset_id}-${event.kind}-${event.timestamp}`}
              className="border-b border-ink-800/60 transition-colors hover:bg-ink-850/60"
            >
              <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-slate-400">
                {formatDateTime(event.timestamp)}
              </td>
              {showAsset && (
                <td className="px-3 py-2 font-medium text-slate-200">{event.symbol}</td>
              )}
              <td className="px-3 py-2 text-slate-300">
                {KIND_LABEL[event.kind] ?? event.kind}
              </td>
              <td className="px-3 py-2">
                <SeverityBadge severity={event.severity} />
              </td>
              <td className="px-3 py-2 text-right font-mono text-xs text-slate-300">
                {event.kind === 'price_zscore'
                  ? formatPrice(event.value)
                  : event.value.toLocaleString('en-US', { maximumFractionDigits: 2 })}
              </td>
              <td className="px-3 py-2 text-right font-mono text-xs text-slate-500">
                {event.kind === 'price_zscore'
                  ? formatPrice(event.baseline)
                  : event.baseline.toLocaleString('en-US', { maximumFractionDigits: 2 })}
              </td>
              <td className="px-3 py-2 text-right font-mono text-xs text-slate-300">
                {event.score.toFixed(2)}
                <span className="ml-1 text-slate-600">
                  {event.kind === 'price_zscore' ? 'z' : 'x'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
