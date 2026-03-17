import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { AUTH_ACCESS_TOKEN_STORAGE_KEY } from '../../../app/authSession.constants';
import { getDashboardSummary } from './getDashboardSummary';
import {
  DASHBOARD_SUMMARY_URL,
  dashboardSummaryServerErrorHandler,
  dashboardSummaryUnauthorizedHandler,
} from '../../../test/msw/handlers';
import { server } from '../../../test/msw/server';

describe('getDashboardSummary', () => {
  it('returns success payload on 200 response', async () => {
    window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, 'dashboard-token');
    server.use(
      http.get(DASHBOARD_SUMMARY_URL, ({ request }) => {
        expect(request.headers.get('authorization')).toBe('Bearer dashboard-token');
        return HttpResponse.json({ status: 'ok' }, { status: 200 });
      }),
    );

    const result = await getDashboardSummary();

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual({ status: 'ok' });
    }
  });

  it('normalizes API failure details and request-id', async () => {
    window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, 'dashboard-token');
    server.use(dashboardSummaryServerErrorHandler);

    const result = await getDashboardSummary();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.message).toBe('dashboard unavailable');
      expect(result.error.requestId).toBe('req-int-1');
      expect(result.error.status).toBe(500);
    }
  });

  it('handles unauthorized response in the same error envelope shape', async () => {
    window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, 'dashboard-token');
    server.use(dashboardSummaryUnauthorizedHandler);

    const result = await getDashboardSummary();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.message).toBe('unauthorized');
      expect(result.error.requestId).toBe('req-int-2');
      expect(result.error.status).toBe(401);
    }
  });
});
