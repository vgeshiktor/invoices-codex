import { expect, test } from '@playwright/test';

test('renders app shell', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  await page.getByRole('button', { name: 'Sign in (stub)' }).click();

  await expect(page.getByRole('heading', { name: 'Invoices Web' })).toBeVisible();
  await page.getByRole('link', { name: 'Providers' }).click();

  await expect(page.getByRole('heading', { name: 'Provider settings' })).toBeVisible();
  await expect(page.getByTestId('provider-card-gmail')).toBeVisible();
  await expect(page.getByTestId('provider-card-outlook')).toBeVisible();
  await expect(
    page.getByTestId('provider-card-gmail').getByRole('button', { name: 'Connect' }),
  ).toBeVisible();
});
