import { describe, expect, it } from 'vitest';
import {
  AUTH_TEST_ACCESS_TOKEN,
  authLoginInvalidCredentialsHandler,
  authMeUnauthorizedExpiredHandler,
  authRefreshUnauthorizedHandler,
} from '../../../test/msw/handlers';
import { server } from '../../../test/msw/server';
import { fetchMe, loginWithPassword, refreshAccessToken } from './authApi';

describe('authApi', () => {
  it('returns login session payload on valid credentials', async () => {
    const result = await loginWithPassword({
      email: 'ops@acme.test',
      password: 'correct-password',
      tenant_slug: 'acme',
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.access_token).toBe(AUTH_TEST_ACCESS_TOKEN);
      expect(result.data.user.email).toBe('ops@acme.test');
      expect(result.data.tenant.slug).toBe('acme');
    }
  });

  it('normalizes auth envelope for invalid credentials', async () => {
    server.use(authLoginInvalidCredentialsHandler);

    const result = await loginWithPassword({
      email: 'ops@acme.test',
      password: 'invalid',
      tenant_slug: 'acme',
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('AUTH_INVALID_CREDENTIALS');
      expect(result.error.message).toBe('Email or password is incorrect.');
      expect(result.error.status).toBe(401);
      expect(result.error.requestId).toBe('req-login-2');
    }
  });

  it('exposes unauthorized status and code for expired access token', async () => {
    server.use(authMeUnauthorizedExpiredHandler);

    const result = await fetchMe('expired-token');

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('AUTH_ACCESS_EXPIRED');
      expect(result.error.message).toBe('Access token expired.');
      expect(result.error.status).toBe(401);
    }
  });

  it('exposes refresh failure details when refresh session is expired', async () => {
    server.use(authRefreshUnauthorizedHandler);

    const result = await refreshAccessToken();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe('AUTH_SESSION_EXPIRED');
      expect(result.error.message).toBe('Session expired.');
      expect(result.error.status).toBe(401);
    }
  });
});
