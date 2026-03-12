import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { getDashboardSummary } from './getDashboardSummary';
import { DASHBOARD_SUMMARY_URL } from '../../../test/msw/handlers';
import { server } from '../../../test/msw/server';

describe('getDashboardSummary', () => {
  it('returns success payload on 200 response', async () => {
    const result = await getDashboardSummary();

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual({ status: 'ok' });
    }
  });

  it('normalizes API failure details and request-id', async () => {
    server.use(
      http.get(DASHBOARD_SUMMARY_URL, () =>
        HttpResponse.json(
          { detail: 'dashboard unavailable' },
          {
            headers: {
              'x-request-id': 'req-int-1',
            },
            status: 500,
          },
        ),
      ),
    );

    const result = await getDashboardSummary();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.message).toBe('dashboard unavailable');
      expect(result.error.requestId).toBe('req-int-1');
      expect(result.error.status).toBe(500);
    }
  });
});
