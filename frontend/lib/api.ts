/**
 * API client.
 *
 * The base URL is configurable so the same frontend works in three setups:
 *
 * 1. Local development, backend on its own port:
 *      NEXT_PUBLIC_API_BASE=http://localhost:8000
 * 2. Single Vercel deployment, Python service reachable at /api (the default):
 *      NEXT_PUBLIC_API_BASE unset, so requests go to /api
 * 3. Backend deployed separately (for example on Render):
 *      NEXT_PUBLIC_API_BASE=https://your-backend.example.com
 */

import type {
  AnomaliesResponse,
  Asset,
  BacktestResponse,
  CompareResponse,
  DetectorConfigPayload,
  DigestResponse,
  SeriesResponse,
} from './types';

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? '/api').replace(/\/$/, '');

/**
 * Turn a path into a URL the browser can always parse.
 *
 * A relative base is joined to an origin before it reaches `fetch`. This is
 * the fix for the original failure: `fetch('/api/assets')` was compiled into a
 * Server Component, where there is no document to resolve a relative URL
 * against, and the WHATWG parser rejected it with "Failed to parse URL from
 * /api/assets". Passing an explicit origin (or calling this from the browser,
 * where `window.location.origin` is read) makes the URL absolute first.
 *
 * When no origin is available it returns the relative path unchanged, which is
 * the correct thing for a browser to resolve itself.
 */
export function resolveUrl(path: string, origin?: string): string {
  const joined = `${API_BASE}${path}`;
  if (/^https?:\/\//i.test(joined)) return joined;

  const base = origin ?? (typeof window !== 'undefined' ? window.location.origin : '');
  if (!base) return joined;

  return new URL(joined, base).toString();
}

/**
 * How a request to the engine failed.
 *
 * - `http`        the engine answered, and answered with an error
 * - `unreachable` no JSON API answered at all: a network failure, or a host
 *                 returning its own HTML error page (a platform 404)
 *
 * The distinction is the whole point. "The engine is broken" and "the engine
 * is not deployed here" need different fixes, and a generic message sends the
 * reader to the wrong one.
 */
export type ApiErrorKind = 'http' | 'unreachable';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly kind: ApiErrorKind,
    readonly url: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const url = resolveUrl(path);

  let response: Response;
  try {
    response = await fetch(url, { signal, cache: 'no-store' });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    throw new ApiError(
      `No response from ${url}: ${(err as Error).message}`,
      0,
      'unreachable',
      url,
    );
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    // The engine always answers with JSON, including its own errors. Anything
    // else is the host's page, which means nothing is serving the API here.
    throw new ApiError(
      `Expected JSON from ${url} but received ${contentType || 'no content type'} (HTTP ${response.status})`,
      response.status,
      'unreachable',
      url,
    );
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body && typeof body.detail === 'string') detail = body.detail;
    } catch {
      // Response claimed JSON but did not parse. The status is all we have.
    }
    throw new ApiError(detail, response.status, 'http', url);
  }

  return (await response.json()) as T;
}

export async function fetchAssets(signal?: AbortSignal): Promise<Asset[]> {
  const payload = await getJson<{ assets: Asset[] }>('/assets', signal);
  return payload.assets ?? [];
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
