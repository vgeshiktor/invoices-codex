import { http, HttpResponse } from 'msw';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:18000';

export const DASHBOARD_SUMMARY_URL = `${API_BASE_URL}/v1/dashboard/summary`;
export const COLLECTION_JOBS_URL = `${API_BASE_URL}/v1/collection-jobs`;

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

export const collectionJobCreateSuccessHandler = http.post(COLLECTION_JOBS_URL, async ({ request }) => {
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
});

export const collectionJobCreateValidationErrorHandler = http.post(COLLECTION_JOBS_URL, () =>
  HttpResponse.json(
    {
      detail: 'providers must be a non-empty list',
    },
    {
      headers: {
        'x-request-id': 'req-col-2',
      },
      status: 400,
    },
  ),
);

export const handlers = [dashboardSummarySuccessHandler];
