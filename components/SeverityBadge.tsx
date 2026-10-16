import type { Severity } from '@/lib/types';
import { SEVERITY_LABEL } from '@/lib/format';

const STYLES: Record<Severity, string> = {
  watch: 'border-signal-watch/40 bg-signal-watch/10 text-signal-watch',
  notable: 'border-signal-notable/40 bg-signal-notable/10 text-signal-notable',
  extreme: 'border-signal-extreme/40 bg-signal-extreme/10 text-signal-extreme',
};

/**
 * Severity badge.
 *
 * Colour is never the only signal: the tier name is always written out, so
 * the badge still reads correctly for someone who cannot distinguish the
 * three hues.
 */
export default function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={`chip ${STYLES[severity]}`}>{SEVERITY_LABEL[severity]}</span>;
}
