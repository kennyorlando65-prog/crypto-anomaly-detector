'use client';

import type { AnomalyEvent, SeriesPoint, Severity } from '@/lib/types';
import { formatDate, formatDateTime, formatPrice } from '@/lib/format';

const SEVERITY_COLOR: Record<Severity, string> = {
  watch: '#e0b341',
  notable: '#e07a3f',
  extreme: '#e05252',
};

const SEVERITY_RADIUS: Record<Severity, number> = {
  watch: 3.5,
  notable: 4.5,
  extreme: 5.5,
};

interface Props {
  series: SeriesPoint[];
  events: AnomalyEvent[];
  symbol: string;
  height?: number;
}

/**
 * Price line with anomaly markers.
 *
 * Drawn as inline SVG rather than pulling in a charting library. The chart is
 * a single line and a set of dots, so a dependency would cost more than it
 * saves, and hand-rolling it keeps the bundle small and the rendering
 * predictable on the free tier.
 *
 * The y-axis is padded by 4 percent at each end so markers on the extremes
 * are not clipped by the viewport edge.
 */
export default function PriceChart({ series, events, symbol, height = 260 }: Props) {
  if (series.length < 2) {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-ink-700 bg-ink-850 text-sm text-slate-500"
        style={{ height }}
      >
        Not enough data to draw a chart.
      </div>
    );
  }

  const width = 1000;
  const padX = 8;
  const padY = 16;

  const prices = series.map((point) => point.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const paddedMin = min - span * 0.04;
  const paddedMax = max + span * 0.04;
  const paddedSpan = paddedMax - paddedMin;

  const x = (index: number) =>
    padX + (index / (series.length - 1)) * (width - padX * 2);
  const y = (price: number) =>
    padY + (1 - (price - paddedMin) / paddedSpan) * (height - padY * 2);

  const linePath = series
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${x(index).toFixed(2)} ${y(point.price).toFixed(2)}`)
    .join(' ');

  const areaPath = `${linePath} L ${x(series.length - 1).toFixed(2)} ${height - padY} L ${x(0).toFixed(2)} ${height - padY} Z`;

  // Map each event onto the nearest series index by date.
  const indexByDate = new Map<string, number>();
  series.forEach((point, index) => indexByDate.set(point.date.slice(0, 10), index));

  const markers = events
    .map((event) => {
      const index = indexByDate.get(event.timestamp.slice(0, 10));
      if (index === undefined) return null;
      return { event, index };
    })
    .filter((item): item is { event: AnomalyEvent; index: number } => item !== null);

  const first = series[0];
  const last = series[series.length - 1];

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height }}
        role="img"
        aria-label={`${symbol} price over ${series.length} days with ${markers.length} flagged anomalies`}
      >
        <defs>
          <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4fb3a5" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#4fb3a5" stopOpacity="0" />
          </linearGradient>
        </defs>

        {[0.25, 0.5, 0.75].map((fraction) => (
          <line
            key={fraction}
            x1={padX}
            x2={width - padX}
            y1={padY + fraction * (height - padY * 2)}
            y2={padY + fraction * (height - padY * 2)}
            stroke="#232936"
            strokeWidth="1"
            strokeDasharray="3 5"
          />
        ))}

        <path d={areaPath} fill="url(#priceFill)" />
        <path d={linePath} fill="none" stroke="#4fb3a5" strokeWidth="1.8" strokeLinejoin="round" />

        {markers.map(({ event, index }) => (
          <g key={`${event.kind}-${event.timestamp}-${event.severity}`}>
            <line
              x1={x(index)}
              x2={x(index)}
              y1={padY}
              y2={height - padY}
              stroke={SEVERITY_COLOR[event.severity]}
              strokeWidth="1"
              strokeOpacity="0.25"
            />
            <circle
              cx={x(index)}
              cy={y(series[index].price)}
              r={SEVERITY_RADIUS[event.severity]}
              fill={SEVERITY_COLOR[event.severity]}
              stroke="#0d0f14"
              strokeWidth="1.5"
            >
              <title>
                {`${formatDateTime(event.timestamp)} - ${event.severity} - ${event.detail}`}
              </title>
            </circle>
          </g>
        ))}
      </svg>

      <div className="mt-1 flex justify-between px-1 text-[11px] text-slate-500">
        <span>{formatDate(first.date)}</span>
        <span className="font-mono">
          low {formatPrice(min)} / high {formatPrice(max)}
        </span>
        <span>{formatDate(last.date)}</span>
      </div>
    </div>
  );
}
