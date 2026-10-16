import type { Severity } from '@/lib/types';
import { SEVERITY_LABEL } from '@/lib/format';

const ACCENT: Record<Severity, string> = {
  extreme: 'text-signal-extreme',
  notable: 'text-signal-notable',
  watch: 'text-signal-watch',
};

/**
 * Severity counters.
 *
 * Always renders all three tiers, including zeros. A missing tier would read
 * as "not measured" rather than "none found", which is a meaningful
 * difference when the whole point is honest reporting.
 */
export default function SeverityCounts({ counts }: { counts: Record<Severity, number> }) {
  const tiers: Severity[] = ['extreme', 'notable', 'watch'];
  return (
    <div className="grid grid-cols-3 gap-3">
      {tiers.map((tier) => (
        <div key={tier} className="card px-4 py-3">
          <div className="label">{SEVERITY_LABEL[tier]}</div>
          <div className={`mt-1 font-mono text-2xl font-semibold ${ACCENT[tier]}`}>
            {counts[tier]}
          </div>
        </div>
      ))}
    </div>
  );
}
