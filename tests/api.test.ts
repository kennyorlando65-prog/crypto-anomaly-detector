import { describe, expect, it } from 'vitest';
import { API_BASE, exportCsvUrl } from '@/lib/api';

describe('API_BASE', () => {
  it('defaults to the same-origin /api path', () => {
    // No NEXT_PUBLIC_API_BASE is set in the test environment, so the client
    // must fall back to the single-project layout.
    expect(API_BASE).toBe('/api');
  });

  it('never ends with a trailing slash', () => {
    expect(API_BASE.endsWith('/')).toBe(false);
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
