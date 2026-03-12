import { http, HttpResponse } from 'msw';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:18000';

export const DASHBOARD_SUMMARY_URL = `${API_BASE_URL}/v1/dashboard/summary`;

export const handlers = [
  http.get(DASHBOARD_SUMMARY_URL, () =>
    HttpResponse.json(
      {
        status: 'ok',
      },
      { status: 200 },
    ),
  ),
];
