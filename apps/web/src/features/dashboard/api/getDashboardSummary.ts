import { apiClient, normalizeApiError, type ApiError } from '../../../shared/api/client';
import {
  dashboardSummaryV1DashboardSummaryGet,
  type DashboardSummaryV1DashboardSummaryGetResponse,
} from '../../../shared/api/generated';

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
  const result = await dashboardSummaryV1DashboardSummaryGet({
    client: apiClient,
  });

  if (result.error !== undefined) {
    return {
      ok: false,
      error: normalizeApiError(result.error, result.response),
    };
  }

  return {
    ok: true,
    data: result.data ?? null,
  };
};
