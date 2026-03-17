import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { AUTH_ACCESS_TOKEN_STORAGE_KEY } from '../../../app/authSession.constants';
import { createCollectionJob } from './createCollectionJob';
import {
  COLLECTION_JOBS_URL,
  collectionJobCreateValidationErrorHandler,
} from '../../../test/msw/handlers';
import { server } from '../../../test/msw/server';

describe('createCollectionJob', () => {
  it('creates a collection job and returns initial run details', async () => {
    window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, 'collection-token');
    server.use(
      http.post(COLLECTION_JOBS_URL, async ({ request }) => {
        expect(request.headers.get('authorization')).toBe('Bearer collection-token');
        const payload = (await request.json()) as { month_scope: string; providers: string[] };

        return HttpResponse.json(
          {
            created_at: '2026-03-20T09:00:00+00:00',
            id: 'col-1',
            month_scope: payload.month_scope,
            providers: payload.providers,
            status: 'queued',
            updated_at: '2026-03-20T09:00:00+00:00',
          },
          {
            headers: {
              'x-request-id': 'req-col-1',
            },
            status: 201,
          },
        );
      }),
    );

    const result = await createCollectionJob({
      month_scope: '2026-03',
      providers: ['gmail'],
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.job.id).toBe('col-1');
      expect(result.job.status).toBe('queued');
      expect(result.job.providers).toEqual(['gmail']);
      expect(result.job.month_scope).toBe('2026-03');
      expect(result.requestId).toBe('req-col-1');
      expect(result.status).toBe(201);
    }
  });

  it('normalizes backend validation errors', async () => {
    window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, 'collection-token');
    server.use(collectionJobCreateValidationErrorHandler);

    const result = await createCollectionJob({
      month_scope: '2026-03',
      providers: [],
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.message).toBe('providers must be a non-empty list');
      expect(result.error.requestId).toBe('req-col-2');
      expect(result.error.status).toBe(400);
    }
  });
});
