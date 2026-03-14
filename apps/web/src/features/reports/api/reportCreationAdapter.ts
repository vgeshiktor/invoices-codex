import { apiClient, normalizeApiError, type ApiError } from '../../../shared/api/client';
import {
  createReportV1ReportsPost,
  listReportsV1ReportsGet,
} from '../../../shared/api/generated';
import {
  REPORT_FORMATS,
  type CreateReportInput,
  type ReportArtifact,
  type ReportFormat,
  type ReportItem,
  type ReportStatus,
} from '../model/report';

type ReportResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError };

export interface ReportCreationAdapter {
  createReport: (input: CreateReportInput) => Promise<ReportResult<ReportItem>>;
  listReports: () => Promise<ReportResult<ReportItem[]>>;
}

const REPORT_STATUS_SET = new Set<ReportStatus>(['queued', 'running', 'succeeded', 'failed']);
const REPORT_FORMAT_SET = new Set<ReportFormat>(REPORT_FORMATS);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const asOptionalString = (value: unknown): string | null =>
  typeof value === 'string' && value.trim().length > 0 ? value : null;

const parseReportStatus = (value: unknown): ReportStatus => {
  if (typeof value !== 'string' || !REPORT_STATUS_SET.has(value as ReportStatus)) {
    throw new Error('Malformed report payload: invalid status');
  }
  return value as ReportStatus;
};

const parseRequestedFormats = (value: unknown): ReportFormat[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((format): format is ReportFormat => REPORT_FORMAT_SET.has(format as ReportFormat));
};

const parseStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
};

const parseFilters = (value: unknown): Record<string, unknown> => {
  if (!isRecord(value)) {
    return {};
  }
  return value;
};

const parseArtifacts = (value: unknown): ReportArtifact[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item): ReportArtifact | null => {
      if (!isRecord(item) || typeof item.id !== 'string' || typeof item.format !== 'string') {
        return null;
      }

      return {
        id: item.id,
        format: item.format,
        bytes: typeof item.bytes === 'number' ? item.bytes : null,
        storagePath: typeof item.storage_path === 'string' ? item.storage_path : '',
      };
    })
    .filter((item): item is ReportArtifact => item !== null);
};

const parseReport = (value: unknown): ReportItem => {
  if (!isRecord(value) || typeof value.id !== 'string') {
    throw new Error('Malformed report payload: missing id');
  }

  return {
    id: value.id,
    status: parseReportStatus(value.status),
    requestedFormats: parseRequestedFormats(value.requested_formats),
    parseJobIds: parseStringArray(value.parse_job_ids),
    filters: parseFilters(value.filters),
    errorMessage: asOptionalString(value.error_message),
    createdAt: asOptionalString(value.created_at),
    startedAt: asOptionalString(value.started_at),
    finishedAt: asOptionalString(value.finished_at),
    artifacts: parseArtifacts(value.artifacts),
  };
};

const parseReportsList = (value: unknown): ReportItem[] => {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    return [];
  }

  return value.items
    .map((item): ReportItem | null => {
      try {
        return parseReport(item);
      } catch {
        return null;
      }
    })
    .filter((item): item is ReportItem => item !== null);
};

export const reportCreationAdapter: ReportCreationAdapter = {
  createReport: async (input) => {
    try {
      const result = await createReportV1ReportsPost({
        body: {
          filters: input.filters,
          formats: input.formats,
          parse_job_ids: input.parseJobIds,
        },
        client: apiClient,
      });

      if (result.error !== undefined) {
        return {
          ok: false,
          error: await normalizeApiError(result.error, result.response),
        };
      }

      return {
        ok: true,
        data: parseReport(result.data),
      };
    } catch (error) {
      return {
        ok: false,
        error: await normalizeApiError(error),
      };
    }
  },

  listReports: async () => {
    try {
      const result = await listReportsV1ReportsGet({
        client: apiClient,
      });

      if (result.error !== undefined) {
        return {
          ok: false,
          error: await normalizeApiError(result.error, result.response),
        };
      }

      return {
        ok: true,
        data: parseReportsList(result.data),
      };
    } catch (error) {
      return {
        ok: false,
        error: await normalizeApiError(error),
      };
    }
  },
};
