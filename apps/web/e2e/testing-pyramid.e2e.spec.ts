import { expect, test } from '@playwright/test';

test('renders app shell', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible();
  await page.getByRole('button', { name: 'Sign in (stub)' }).click();

  await expect(page.getByRole('heading', { name: 'Invoices Web' })).toBeVisible();
  await page.getByRole('link', { name: 'Collections' }).click();

  await expect(page.getByRole('heading', { name: 'Collect current month' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start collection run' })).toBeVisible();
  await expect(page.getByLabel('Month scope')).toBeVisible();
});
