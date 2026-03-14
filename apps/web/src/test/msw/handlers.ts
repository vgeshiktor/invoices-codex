import { http, HttpResponse } from 'msw';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:18000';

export const AUTH_LOGIN_URL = `${API_BASE_URL}/auth/login`;
export const AUTH_REFRESH_URL = `${API_BASE_URL}/auth/refresh`;
export const AUTH_LOGOUT_URL = `${API_BASE_URL}/auth/logout`;
export const AUTH_ME_URL = `${API_BASE_URL}/v1/me`;

export const DASHBOARD_SUMMARY_URL = `${API_BASE_URL}/v1/dashboard/summary`;
export const COLLECTION_JOBS_URL = `${API_BASE_URL}/v1/collection-jobs`;

export const AUTH_TEST_ACCESS_TOKEN = 'auth-test-access-token';
export const AUTH_TEST_REFRESHED_ACCESS_TOKEN = 'auth-test-refreshed-access-token';

const AUTH_TEST_USER = {
  id: 'usr_1',
  email: 'ops@acme.test',
  full_name: 'Acme Ops',
  role: 'admin',
  status: 'active',
};

const AUTH_TEST_TENANT = {
  id: 'ten_1',
  slug: 'acme',
  name: 'Acme Ltd',
};

const AUTH_TEST_SESSION = {
  session_id: 'ses_1',
  access_expires_at: '2026-03-14T10:15:00Z',
  refresh_expires_at: '2026-04-13T10:00:00Z',
};

const unauthorizedEnvelope = (code: string, message: string, requestId: string) =>
  HttpResponse.json(
    {
      error: {
        code,
        details: {},
        message,
        request_id: requestId,
      },
    },
    {
      headers: {
        'x-request-id': requestId,
      },
      status: 401,
    },
  );

export const authLoginSuccessHandler = http.post(AUTH_LOGIN_URL, async () =>
  HttpResponse.json(
    {
      access_token: AUTH_TEST_ACCESS_TOKEN,
      expires_in: 900,
      session: AUTH_TEST_SESSION,
      tenant: AUTH_TEST_TENANT,
      token_type: 'Bearer',
      user: AUTH_TEST_USER,
    },
    {
      headers: {
        'x-request-id': 'req-login-1',
      },
      status: 200,
    },
  ),
);

export const authLoginInvalidCredentialsHandler = http.post(AUTH_LOGIN_URL, async () =>
  HttpResponse.json(
    {
      error: {
        code: 'AUTH_INVALID_CREDENTIALS',
        details: {},
        message: 'Email or password is incorrect.',
        request_id: 'req-login-2',
      },
    },
    {
      headers: {
        'x-request-id': 'req-login-2',
      },
      status: 401,
    },
  ),
);

export const authMeSuccessHandler = http.get(AUTH_ME_URL, async ({ request }) => {
  const authorization = request.headers.get('authorization');

  if (
    authorization !== `Bearer ${AUTH_TEST_ACCESS_TOKEN}` &&
    authorization !== `Bearer ${AUTH_TEST_REFRESHED_ACCESS_TOKEN}`
  ) {
    return unauthorizedEnvelope(
      'AUTH_ACCESS_INVALID',
      'Access token is invalid.',
      'req-me-unauthorized',
    );
  }

  return HttpResponse.json(
    {
      session: AUTH_TEST_SESSION,
      tenant: AUTH_TEST_TENANT,
      user: AUTH_TEST_USER,
    },
    {
      headers: {
        'x-request-id': 'req-me-1',
      },
      status: 200,
    },
  );
});

export const authMeUnauthorizedExpiredHandler = http.get(AUTH_ME_URL, async () =>
  unauthorizedEnvelope('AUTH_ACCESS_EXPIRED', 'Access token expired.', 'req-me-2'),
);

export const authRefreshSuccessHandler = http.post(AUTH_REFRESH_URL, async () =>
  HttpResponse.json(
    {
      access_token: AUTH_TEST_REFRESHED_ACCESS_TOKEN,
      expires_in: 900,
      session: AUTH_TEST_SESSION,
      token_type: 'Bearer',
    },
    {
      headers: {
        'x-request-id': 'req-refresh-1',
      },
      status: 200,
    },
  ),
);

export const authRefreshUnauthorizedHandler = http.post(AUTH_REFRESH_URL, async () =>
  unauthorizedEnvelope('AUTH_SESSION_EXPIRED', 'Session expired.', 'req-refresh-2'),
);

export const authLogoutSuccessHandler = http.post(
  AUTH_LOGOUT_URL,
  async () => new HttpResponse(null, { status: 204 }),
);

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

export const handlers = [
  authLoginSuccessHandler,
  authLogoutSuccessHandler,
  authMeSuccessHandler,
  authRefreshSuccessHandler,
  collectionJobCreateSuccessHandler,
  dashboardSummarySuccessHandler,
];
