export const AUTH_ACCESS_TOKEN_STORAGE_KEY = 'fe_auth_access_token';

export type AuthSessionStatus =
  | 'checking'
  | 'authenticated'
  | 'unauthenticated'
  | 'error';
