import { AUTH_ACCESS_TOKEN_STORAGE_KEY } from '../../app/authSession.constants';
import { frontendEnv } from '../config/env';

const readStoredAccessToken = (): string | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  const raw = window.localStorage.getItem(AUTH_ACCESS_TOKEN_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  const value = raw.trim();
  return value.length > 0 ? value : null;
};

export const getRuntimeAuthHeaders = (): Record<string, string> | undefined => {
  const accessToken = readStoredAccessToken();
  if (accessToken) {
    return {
      Authorization: `Bearer ${accessToken}`,
    };
  }

  if (frontendEnv.apiKey) {
    return {
      'X-API-Key': frontendEnv.apiKey,
    };
  }

  return undefined;
};
