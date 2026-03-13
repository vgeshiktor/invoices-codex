import { expect, test } from '@playwright/test';

test('renders app shell', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Invoices Web' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Fetch dashboard summary' })).toBeVisible();
});
