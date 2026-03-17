import { apiClient, normalizeApiError, type ApiError } from '../../../shared/api/client';
import { getRuntimeAuthHeaders } from '../../../shared/api/runtimeAuth';
import type { CollectionJob, CollectionJobStatus, CollectionProvider } from './createCollectionJob';

export type GetCollectionJobResult =
  | {
      ok: true;
      job: CollectionJob;
    }
  | {
      ok: false;
      error: ApiError;
    };

const COLLECTION_JOB_STATUS_SET = new Set<CollectionJobStatus>([
  'queued',
  'running',
  'succeeded',
  'failed',
]);

const COLLECTION_PROVIDER_SET = new Set<CollectionProvider>(['gmail', 'outlook']);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const asOptionalString = (value: unknown): string | null =>
  typeof value === 'string' && value.trim().length > 0 ? value : null;

const asOptionalNumber = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const parseStatus = (value: unknown): CollectionJobStatus | null => {
  if (typeof value !== 'string' || !COLLECTION_JOB_STATUS_SET.has(value as CollectionJobStatus)) {
    return null;
  }

  return value as CollectionJobStatus;
};

const parseProviders = (value: unknown): CollectionProvider[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter(
    (provider): provider is CollectionProvider =>
      typeof provider === 'string' && COLLECTION_PROVIDER_SET.has(provider as CollectionProvider),
  );
};

const parseStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
};

const parseCollectionJob = (value: unknown): CollectionJob | null => {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.month_scope !== 'string') {
    return null;
  }

  const status = parseStatus(value.status);
  if (status === null) {
    return null;
  }

  return {
    created_at: asOptionalString(value.created_at),
    error_message: asOptionalString(value.error_message),
    files_discovered: asOptionalNumber(value.files_discovered),
    files_downloaded: asOptionalNumber(value.files_downloaded),
    finished_at: asOptionalString(value.finished_at),
    id: value.id,
    month_scope: value.month_scope,
    parse_job_ids: parseStringArray(value.parse_job_ids),
    providers: parseProviders(value.providers),
    started_at: asOptionalString(value.started_at),
    status,
    updated_at: asOptionalString(value.updated_at),
  };
};

// OpenAPI snapshot currently does not include GET /v1/collection-jobs/{id};
// keep a typed adapter here until the schema is refreshed.
export const getCollectionJob = async (
  collectionJobId: string,
): Promise<GetCollectionJobResult> => {
  try {
    const result = await apiClient.get<CollectionJob, unknown>({
      headers: getRuntimeAuthHeaders(),
      url: `/v1/collection-jobs/${collectionJobId}`,
    });

    if (result.error !== undefined) {
      return {
        ok: false,
        error: await normalizeApiError(result.error, result.response),
      };
    }

    const job = parseCollectionJob(result.data);
    if (job === null) {
      return {
        ok: false,
        error: {
          message: 'Collection detail response was malformed',
        },
      };
    }

    return {
      ok: true,
      job,
    };
  } catch (error) {
    return {
      ok: false,
      error: await normalizeApiError(error),
    };
  }
};
