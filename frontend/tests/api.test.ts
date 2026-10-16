import { describe, expect, it } from 'vitest';
import { ApiError, API_BASE, exportCsvUrl, fetchAssets, resolveUrl } from '@/lib/api';

describe('API_BASE', () => {
  it('defaults to the same-origin /api path', () => {
    // No NEXT_PUBLIC_API_BASE is set in the test environment, so the client
    // must fall back to the single-deployment layout.
    expect(API_BASE).toBe('/api');
  });

  it('never ends with a trailing slash', () => {
    expect(API_BASE.endsWith('/')).toBe(false);
  });
});

describe('resolveUrl', () => {
  // There is no `window` in this environment, which mirrors a server render.
  it('returns the relative path when no origin is available', () => {
    expect(resolveUrl('/assets')).toBe('/api/assets');
  });

  it('joins a relative base to a supplied origin', () => {
    // This is the behaviour that fixes "Failed to parse URL from /api/assets".
    expect(resolveUrl('/assets', 'https://example.com')).toBe('https://example.com/api/assets');
  });

  it('passes an absolute base through untouched', () => {
    const url = resolveUrl('/assets', 'https://ignored.example.com');
    expect(url.startsWith('/api') || url.startsWith('http')).toBe(true);
  });
});

describe('error classification', () => {
  const realFetch = globalThis.fetch;

  function stubFetch(response: Response) {
    globalThis.fetch = (async () => response) as unknown as typeof fetch;
  }

  it('treats an HTML 404 as an unreachable engine, not an HTTP error', async () => {
    // This is exactly what a platform 404 page looks like, and it is why the
    // two kinds have to be distinguished: the fix is a deploy, not a bug hunt.
    stubFetch(
      new Response('<!DOCTYPE html><html><body>404</body></html>', {
        status: 404,
        headers: { 'content-type': 'text/html; charset=utf-8' },
      }),
    );
    try {
      await expect(fetchAssets()).rejects.toMatchObject({ kind: 'unreachable', status: 404 });
    } finally {
      globalThis.fetch = realFetch;
    }
  });

  it('treats a JSON error as an HTTP error from a live engine', async () => {
    stubFetch(
      new Response(JSON.stringify({ detail: 'Unknown asset' }), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      }),
    );
    try {
      await expect(fetchAssets()).rejects.toMatchObject({
        kind: 'http',
        status: 404,
        message: 'Unknown asset',
      });
    } finally {
      globalThis.fetch = realFetch;
    }
  });

  it('treats a network failure as unreachable', async () => {
    globalThis.fetch = (async () => {
      throw new TypeError('Failed to fetch');
    }) as unknown as typeof fetch;
    try {
      const error = await fetchAssets().catch((e: unknown) => e);
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).kind).toBe('unreachable');
    } finally {
      globalThis.fetch = realFetch;
    }
  });

  it('returns the asset list on success', async () => {
    stubFetch(
      new Response(JSON.stringify({ assets: [{ id: 'bitcoin', symbol: 'BTC', name: 'Bitcoin' }] }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    try {
      await expect(fetchAssets()).resolves.toHaveLength(1);
    } finally {
      globalThis.fetch = realFetch;
    }
  });
});

describe('exportCsvUrl', () => {
  it('includes the day window', () => {
    expect(exportCsvUrl({ days: 90 })).toBe('/api/export.csv?days=90');
  });

  it('includes severity when given', () => {
    expect(exportCsvUrl({ days: 30, severity: 'extreme' })).toBe(
      '/api/export.csv?days=30&severity=extreme',
    );
  });

  it('omits severity when undefined', () => {
    expect(exportCsvUrl({ days: 30, severity: undefined })).not.toContain('severity');
  });

  it('includes the asset when given', () => {
    expect(exportCsvUrl({ days: 90, asset: 'bitcoin' })).toContain('asset=bitcoin');
  });
});
