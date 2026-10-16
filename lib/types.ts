/**
 * Shared types for the dashboard.
 *
 * These mirror the FastAPI response shapes exactly. If the API changes, this
 * file is the single place the frontend has to follow.
 */

export type Severity = 'watch' | 'notable' | 'extreme';

export type DetectorKind = 'price_zscore' | 'volume_spike' | 'volatility_regime';

export interface AnomalyEvent {
  asset_id: string;
  symbol: string;
  kind: DetectorKind;
  timestamp: string;
  severity: Severity;
  value: number;
  baseline: number;
  score: number;
  direction: 'up' | 'down';
  detail: string;
}

export interface SeriesPoint {
  date: string;
  price: number;
  volume: number;
}

export interface Asset {
  id: string;
  symbol: string;
  name: string;
  price: number | null;
  market_cap: number | null;
  volume_24h: number | null;
  change_24h: number | null;
  change_7d: number | null;
}

export interface Summary {
  total: number;
  by_severity: Record<Severity, number>;
  by_kind: Record<string, number>;
}

export interface SeriesResponse {
  asset: { id: string; symbol: string; name: string };
  days: number;
  series: SeriesPoint[];
  events: AnomalyEvent[];
  summary: Summary;
}

export interface AnomaliesResponse {
  events: AnomalyEvent[];
  summary: Summary;
  filters: { days: number; severity: string | null; asset: string | null; kind: string | null };
  errors: string[];
  disclaimer: string;
}

export interface BacktestAsset {
  asset_id: string;
  symbol: string;
  days: number;
  observations: number;
  total_events: number;
  by_severity: Record<Severity, number>;
  by_kind: Record<string, number>;
  events_per_week: number;
  events: AnomalyEvent[];
}

export interface BacktestResponse {
  days: number;
  assets: BacktestAsset[];
  totals: { events: number; events_per_week: number; assets: number };
  errors: string[];
  note: string;
}

export interface DigestResponse {
  generated_at: string;
  window_hours: number;
  counts: Record<Severity, number>;
  total: number;
  events: AnomalyEvent[];
  text: string;
  errors: string[];
}

export interface CompareResponse {
  days: number;
  a: { asset: { id: string; symbol: string; name: string }; series: SeriesPoint[]; events: AnomalyEvent[]; summary: Summary };
  b: { asset: { id: string; symbol: string; name: string }; series: SeriesPoint[]; events: AnomalyEvent[]; summary: Summary };
}

export interface DetectorConfigPayload {
  detector: Record<string, number | boolean>;
  disclaimer: string;
}
