import { describe, expect, it } from 'vitest';
import { createCollectionJob } from './createCollectionJob';
import {
  collectionJobCreateSuccessHandler,
  collectionJobCreateValidationErrorHandler,
} from '../../../test/msw/handlers';
import { server } from '../../../test/msw/server';

describe('createCollectionJob', () => {
  it('creates a collection job and returns initial run details', async () => {
    server.use(collectionJobCreateSuccessHandler);

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
