import { expect, test } from '@playwright/test';

const ACCESS_TOKEN = 'e2e-access-token';
const REFRESHED_TOKEN = 'e2e-refreshed-token';

const authHeaders = {
  'access-control-allow-credentials': 'true',
  'access-control-allow-origin': 'http://127.0.0.1:4173',
  'content-type': 'application/json',
  'x-request-id': 'req-e2e-1',
};

test('supports login, protected navigation, and logout flow', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());

  await page.route('**/auth/login', async (route) => {
    await route.fulfill({
      body: JSON.stringify({
        access_token: ACCESS_TOKEN,
        expires_in: 900,
        session: {
          access_expires_at: '2026-03-14T10:15:00Z',
          refresh_expires_at: '2026-04-13T10:00:00Z',
          session_id: 'ses-e2e-1',
        },
        tenant: {
          id: 'ten-e2e-1',
          name: 'Acme Ltd',
          slug: 'acme',
        },
        token_type: 'Bearer',
        user: {
          email: 'ops@acme.test',
          full_name: 'Acme Ops',
          id: 'usr-e2e-1',
          role: 'admin',
          status: 'active',
        },
      }),
      headers: authHeaders,
      status: 200,
    });
  });

  await page.route('**/auth/refresh', async (route) => {
    await route.fulfill({
      body: JSON.stringify({
        access_token: REFRESHED_TOKEN,
        expires_in: 900,
        session: {
          access_expires_at: '2026-03-14T10:30:00Z',
          refresh_expires_at: '2026-04-13T10:00:00Z',
          session_id: 'ses-e2e-1',
        },
        token_type: 'Bearer',
      }),
      headers: authHeaders,
      status: 200,
    });
  });

  await page.route('**/v1/me', async (route) => {
    const authorization = route.request().headers().authorization;
    if (authorization !== `Bearer ${ACCESS_TOKEN}` && authorization !== `Bearer ${REFRESHED_TOKEN}`) {
      await route.fulfill({
        body: JSON.stringify({
          error: {
            code: 'AUTH_ACCESS_INVALID',
            details: {},
            message: 'Access token is invalid.',
            request_id: 'req-e2e-2',
          },
        }),
        headers: authHeaders,
        status: 401,
      });
      return;
    }

    await route.fulfill({
      body: JSON.stringify({
        session: {
          access_expires_at: '2026-03-14T10:15:00Z',
          refresh_expires_at: '2026-04-13T10:00:00Z',
          session_id: 'ses-e2e-1',
        },
        tenant: {
          id: 'ten-e2e-1',
          name: 'Acme Ltd',
          slug: 'acme',
        },
        user: {
          email: 'ops@acme.test',
          full_name: 'Acme Ops',
          id: 'usr-e2e-1',
          role: 'admin',
          status: 'active',
        },
      }),
      headers: authHeaders,
      status: 200,
    });
  });

  await page.route('**/auth/logout', async (route) => {
    await route.fulfill({
      headers: {
        'access-control-allow-credentials': 'true',
        'access-control-allow-origin': 'http://127.0.0.1:4173',
        'x-request-id': 'req-e2e-3',
      },
      status: 204,
    });
  });

  await page.route('**/v1/collection-jobs', async (route) => {
    await route.fulfill({
      body: JSON.stringify({
        created_at: '2026-03-20T09:00:00+00:00',
        id: 'col-e2e-1',
        month_scope: '2026-03',
        providers: ['gmail', 'outlook'],
        status: 'queued',
        updated_at: '2026-03-20T09:00:00+00:00',
      }),
      headers: authHeaders,
      status: 201,
    });
  });

  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  await page.getByLabel('Tenant slug').fill('acme');
  await page.getByLabel('Email').fill('ops@acme.test');
  await page.getByLabel('Password').fill('correct-password');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByRole('heading', { name: 'Invoices Web' })).toBeVisible();
  await page.getByRole('link', { name: 'Collections' }).click();

  await expect(page.getByRole('heading', { name: 'Collect current month' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start collection run' })).toBeVisible();
  await expect(page.getByLabel('Month scope')).toBeVisible();
  await page.getByRole('button', { name: 'Start collection run' }).click();
  await expect(page.getByRole('heading', { name: 'Run started' })).toBeVisible();
  // Expect API to return status 'queued' for the initial run.
  await expect(page.getByText(/queued/i)).toBeVisible();
  // CollectionWizardPage integration test already "shows error state when submit request fails".

  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  await expect(page.getByText('Signed out successfully.')).toBeVisible();
});
