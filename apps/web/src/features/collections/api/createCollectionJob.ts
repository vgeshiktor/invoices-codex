import { apiClient, getApiRequestId, normalizeApiError, type ApiError } from '../../../shared/api/client';
import { getRuntimeAuthHeaders } from '../../../shared/api/runtimeAuth';

export type CollectionProvider = 'gmail' | 'outlook';

export type CollectionJobStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export interface CollectionJob {
  id: string;
  status: CollectionJobStatus;
  providers: CollectionProvider[];
  month_scope: string;
  created_at?: string | null;
  updated_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  files_discovered?: number | null;
  files_downloaded?: number | null;
  parse_job_ids?: string[];
}

export interface CreateCollectionJobRequest {
  providers: CollectionProvider[];
  month_scope: string;
}

export type CreateCollectionJobResult =
  | {
      ok: true;
      requestId?: string;
      status: number;
      job: CollectionJob;
    }
  | {
      ok: false;
      error: ApiError;
    };

const createIdempotencyKey = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `collection-${crypto.randomUUID()}`;
  }

  return `collection-${Date.now()}`;
};

// OpenAPI snapshot currently does not include /v1/collection-jobs;
// use a contract-typed adapter until schema is updated.
export const createCollectionJob = async (
  payload: CreateCollectionJobRequest,
): Promise<CreateCollectionJobResult> => {
  const result = await apiClient.post<CollectionJob, unknown>({
    body: payload,
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': createIdempotencyKey(),
      ...(getRuntimeAuthHeaders() ?? {}),
    },
    url: '/v1/collection-jobs',
  });

  if (result.error !== undefined) {
    return {
      ok: false,
      error: await normalizeApiError(result.error, result.response),
    };
  }

  if (result.data === undefined) {
    return {
      ok: false,
      error: {
        message: 'Collection create response was empty',
        requestId: getApiRequestId(result.response),
        status: result.response.status,
      },
    };
  }

  return {
    ok: true,
    job: result.data,
    requestId: getApiRequestId(result.response),
    status: result.response.status,
  };
};
