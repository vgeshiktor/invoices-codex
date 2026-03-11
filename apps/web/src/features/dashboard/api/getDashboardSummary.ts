import { apiClient, getApiRequestId, normalizeApiError, type ApiError } from '../../../shared/api/client';
import {
  dashboardSummaryV1DashboardSummaryGet,
  type DashboardSummaryV1DashboardSummaryGetResponse,
} from '../../../shared/api/generated';

type DashboardSummarySuccess = {
  data: DashboardSummaryV1DashboardSummaryGetResponse | null;
  requestId?: string;
  status: number;
};

type DashboardSummaryFailure = {
  error: ApiError;
  requestId?: string;
  status?: number;
};

export type DashboardSummaryResult = DashboardSummarySuccess | DashboardSummaryFailure;

export const getDashboardSummary = async (): Promise<DashboardSummaryResult> => {
  const result = await dashboardSummaryV1DashboardSummaryGet({
    client: apiClient,
  });

  if (result.error !== undefined) {
    return {
      error: normalizeApiError(result.error, result.response),
      requestId: getApiRequestId(result.response),
      status: result.response?.status,
    };
  }

  return {
    data: result.data ?? null,
    requestId: getApiRequestId(result.response),
    status: result.response.status,
  };
};
