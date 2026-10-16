/**
 * API client.
 *
 * The base URL is configurable so the same frontend works in three setups:
 *
 * 1. Local development, backend on its own port:
 *      NEXT_PUBLIC_API_BASE=http://localhost:8000
 * 2. Single Vercel project, Python function at /api (the default):
 *      NEXT_PUBLIC_API_BASE unset, so requests go to /api
 * 3. Backend deployed separately (for example on Render):
 *      NEXT_PUBLIC_API_BASE=https://your-backend.example.com
 *
 * Keeping this configurable is what stops the frontend from being welded to
 * one hosting arrangement.
 */

import type {
  AnomaliesResponse,
  BacktestResponse,
  CompareResponse,
  DetectorConfigPayload,
  DigestResponse,
  SeriesResponse,
} from './types';

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? '/api').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { signal, cache: 'no-store' });
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body && typeof body.detail === 'string') detail = body.detail;
    } catch {
      // Response was not JSON. The status message is all we have.
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export function fetchSeries(coinId: string, days: number, signal?: AbortSignal) {
  return getJson<SeriesResponse>(`/series/${encodeURIComponent(coinId)}?days=${days}`, signal);
}

export function fetchAnomalies(
  params: { days: number; severity?: string; asset?: string; kind?: string },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({ days: String(params.days) });
  if (params.severity) query.set('severity', params.severity);
  if (params.asset) query.set('asset', params.asset);
  if (params.kind) query.set('kind', params.kind);
  return getJson<AnomaliesResponse>(`/anomalies?${query.toString()}`, signal);
}

export function fetchBacktest(days: number, asset?: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ days: String(days) });
  if (asset) query.set('asset', asset);
  return getJson<BacktestResponse>(`/backtest?${query.toString()}`, signal);
}

export function fetchDigest(hours: number, days: number, signal?: AbortSignal) {
  return getJson<DigestResponse>(`/digest?hours=${hours}&days=${days}`, signal);
}

export function fetchCompare(a: string, b: string, days: number, signal?: AbortSignal) {
  return getJson<CompareResponse>(`/compare?a=${a}&b=${b}&days=${days}`, signal);
}

export function fetchConfig(signal?: AbortSignal) {
  return getJson<DetectorConfigPayload>('/config', signal);
}

export function exportCsvUrl(params: { days: number; severity?: string; asset?: string }) {
  const query = new URLSearchParams({ days: String(params.days) });
  if (params.severity) query.set('severity', params.severity);
  if (params.asset) query.set('asset', params.asset);
  return `${API_BASE}/export.csv?${query.toString()}`;
}
