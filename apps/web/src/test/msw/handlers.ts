import { http, HttpResponse } from 'msw';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:18000';

export const DASHBOARD_SUMMARY_URL = `${API_BASE_URL}/v1/dashboard/summary`;

export const dashboardSummarySuccessHandler = http.get(DASHBOARD_SUMMARY_URL, () =>
  HttpResponse.json(
    {
      status: 'ok',
    },
    { status: 200 },
  ),
);

export const dashboardSummaryServerErrorHandler = http.get(DASHBOARD_SUMMARY_URL, () =>
  HttpResponse.json(
    {
      detail: 'dashboard unavailable',
    },
    {
      headers: {
        'x-request-id': 'req-int-1',
      },
      status: 500,
    },
  ),
);

export const dashboardSummaryUnauthorizedHandler = http.get(DASHBOARD_SUMMARY_URL, () =>
  HttpResponse.json(
    {
      detail: 'unauthorized',
    },
    {
      headers: {
        'x-request-id': 'req-int-2',
      },
      status: 401,
    },
  ),
);

export const handlers = [dashboardSummarySuccessHandler];
