import { describe, expect, it } from 'vitest';
import { getDashboardSummary } from './getDashboardSummary';
import {
  dashboardSummaryServerErrorHandler,
  dashboardSummaryUnauthorizedHandler,
} from '../../../test/msw/handlers';
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
