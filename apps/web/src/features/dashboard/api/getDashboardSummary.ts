import { apiClient, normalizeApiError, type ApiError } from '../../../shared/api/client';
import type { DashboardSummaryV1DashboardSummaryGetResponse } from '../../../shared/api/generated';
import { getRuntimeAuthHeaders } from '../../../shared/api/runtimeAuth';

export type DashboardSummaryResult =
  | {
      ok: true;
      data: DashboardSummaryV1DashboardSummaryGetResponse | null;
    }
  | {
      ok: false;
      error: ApiError;
    };

export const getDashboardSummary = async (): Promise<DashboardSummaryResult> => {
  try {
    const result = await apiClient.get<DashboardSummaryV1DashboardSummaryGetResponse, unknown>({
      headers: getRuntimeAuthHeaders(),
      url: '/v1/dashboard/summary',
    });

    if (result.error !== undefined) {
      return {
        ok: false,
        error: await normalizeApiError(result.error, result.response),
      };
    }

    return {
      ok: true,
      data: result.data ?? null,
    };
  } catch (error) {
    return {
      ok: false,
      error: await normalizeApiError(error),
    };
  }
};
