import { expect, test } from '@playwright/test';

const ACCESS_TOKEN = 'mvp-access-token';

const AUTH_HEADERS = {
  'access-control-allow-credentials': 'true',
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'content-type': 'application/json',
  'x-request-id': 'req-mvp-smoke',
};

const LOGIN_RESPONSE_BODY = {
  access_token: ACCESS_TOKEN,
  expires_in: 900,
  session: {
    access_expires_at: '2026-03-17T10:15:00Z',
    refresh_expires_at: '2026-04-16T10:00:00Z',
    session_id: 'ses-mvp-smoke-1',
  },
  tenant: {
    id: 'ten-mvp-smoke-1',
    name: 'Acme Ltd',
    slug: 'acme',
  },
  token_type: 'Bearer',
  user: {
    email: 'ops@acme.test',
    full_name: 'Acme Ops',
    id: 'usr-mvp-smoke-1',
    role: 'admin',
    status: 'active',
  },
};

const PROVIDERS_RESPONSE_BODY = {
  items: [
    {
      config: {},
      connection_status: 'connected',
      created_at: '2026-03-17T09:55:00+00:00',
      display_name: 'Gmail',
      id: 'prov-gmail-1',
      last_error_code: null,
      last_error_message: null,
      last_successful_sync_at: '2026-03-17T09:50:00+00:00',
      provider_type: 'gmail',
      tenant_id: 'ten-mvp-smoke-1',
      token_expires_at: '2026-03-20T00:00:00+00:00',
      updated_at: '2026-03-17T10:00:00+00:00',
    },
    {
      config: {},
      connection_status: 'disconnected',
      created_at: '2026-03-17T09:55:00+00:00',
      display_name: 'Outlook',
      id: 'prov-outlook-1',
      last_error_code: null,
      last_error_message: null,
      last_successful_sync_at: null,
      provider_type: 'outlook',
      tenant_id: 'ten-mvp-smoke-1',
      token_expires_at: null,
      updated_at: '2026-03-17T10:00:00+00:00',
    },
  ],
  limit: 10,
  offset: 0,
  total: 2,
};

const TEST_CONNECTION_RESPONSE_BODY = {
  message: 'provider connection verified',
  provider: {
    config: {},
    connection_status: 'connected',
    created_at: '2026-03-17T09:55:00+00:00',
    display_name: 'Gmail',
    id: 'prov-gmail-1',
    last_error_code: null,
    last_error_message: null,
    last_successful_sync_at: '2026-03-17T10:01:00+00:00',
    provider_type: 'gmail',
    tenant_id: 'ten-mvp-smoke-1',
    token_expires_at: '2026-03-20T00:00:00+00:00',
    updated_at: '2026-03-17T10:01:00+00:00',
  },
  request_id: 'req-mvp-smoke-test-connection',
  status: 'success',
  tested_at: '2026-03-17T10:01:00+00:00',
};

const DASHBOARD_RESPONSE_BODY = {
  totals: {
    parse_jobs: 3,
    reports: 2,
  },
};

test('mvp smoke: login -> providers -> test connection -> dashboard', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());

  await page.route('**/auth/login', async (route) => {
    await route.fulfill({
      body: JSON.stringify(LOGIN_RESPONSE_BODY),
      headers: AUTH_HEADERS,
      status: 200,
    });
  });

  await page.route('**/v1/providers?**', async (route) => {
    await route.fulfill({
      body: JSON.stringify(PROVIDERS_RESPONSE_BODY),
      headers: AUTH_HEADERS,
      status: 200,
    });
  });

  await page.route('**/v1/providers', async (route) => {
    await route.fulfill({
      body: JSON.stringify(PROVIDERS_RESPONSE_BODY),
      headers: AUTH_HEADERS,
      status: 200,
    });
  });

  let testConnectionCalls = 0;
  await page.route('**/v1/providers/*/test-connection', async (route) => {
    testConnectionCalls += 1;
    await route.fulfill({
      body: JSON.stringify(TEST_CONNECTION_RESPONSE_BODY),
      headers: AUTH_HEADERS,
      status: 200,
    });
  });

  await page.route('**/v1/dashboard/summary', async (route) => {
    await route.fulfill({
      body: JSON.stringify(DASHBOARD_RESPONSE_BODY),
      headers: AUTH_HEADERS,
      status: 200,
    });
  });

  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  await page.getByLabel('Tenant slug').fill('acme');
  await page.getByLabel('Email').fill('ops@acme.test');
  await page.getByLabel('Password').fill('correct-password');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByRole('heading', { name: 'Invoices Web' })).toBeVisible();

  await page.getByRole('link', { name: 'Providers' }).click();
  await expect(page.getByRole('heading', { name: 'Provider settings' })).toBeVisible();
  const gmailCard = page.getByTestId('provider-card-gmail');
  await expect(gmailCard).toBeVisible();

  const testConnectionButton = gmailCard.getByRole('button', { name: /test connection/i });
  await expect(testConnectionButton).toBeVisible();
  await testConnectionButton.click();
  await expect.poll(() => testConnectionCalls).toBeGreaterThan(0);
  const resultPanel = gmailCard.getByTestId('provider-test-result-gmail');
  await expect(resultPanel).toContainText('Success');
  await expect(resultPanel).toContainText('provider connection verified');
  await expect(resultPanel).toContainText('request-id: req-mvp-smoke-test-connection');

  await page.getByRole('link', { name: 'Dashboard' }).click();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await page.getByRole('button', { name: 'Fetch dashboard summary' }).click();
  await expect(page.getByText('Dashboard summary fetched successfully.')).toBeVisible();
});

test('mvp smoke failure path: invalid credentials keep user on login', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());

  await page.route('**/auth/login', async (route) => {
    await route.fulfill({
      body: JSON.stringify({
        error: {
          code: 'AUTH_INVALID_CREDENTIALS',
          details: {},
          message: 'Invalid credentials.',
          request_id: 'req-mvp-smoke-invalid-login',
        },
      }),
      headers: AUTH_HEADERS,
      status: 401,
    });
  });

  await page.goto('/login');

  await page.getByLabel('Tenant slug').fill('acme');
  await page.getByLabel('Email').fill('ops@acme.test');
  await page.getByLabel('Password').fill('wrong-password');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Invalid credentials');
});
