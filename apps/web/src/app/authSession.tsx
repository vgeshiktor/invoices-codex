import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  fetchMe,
  loginWithPassword,
  logoutSession,
  refreshAccessToken,
  type AuthApiError,
  type LoginRequest,
} from '../features/auth/api/authApi';
import {
  AuthSessionContext,
  type AuthActionResult,
  type AuthSessionContextValue,
  type AuthState,
  type AuthenticatedSession,
} from './authSession.context';
import { AUTH_ACCESS_TOKEN_STORAGE_KEY } from './authSession.constants';

const AUTH_EXPIRED_CODES = new Set([
  'AUTH_ACCESS_EXPIRED',
  'AUTH_ACCESS_INVALID',
  'AUTH_ACCESS_MISSING',
  'AUTH_REFRESH_INVALID',
  'AUTH_REFRESH_MISSING',
  'AUTH_SESSION_EXPIRED',
  'AUTH_SESSION_REVOKED',
]);

const defaultState: AuthState = {
  errorMessage: null,
  isWorking: false,
  notice: null,
  session: null,
  status: 'checking',
};

const readStoredAccessToken = (): string | null => {
  const raw = window.localStorage.getItem(AUTH_ACCESS_TOKEN_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  const value = raw.trim();
  return value.length > 0 ? value : null;
};

const storeAccessToken = (accessToken: string): void => {
  window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, accessToken);
};

const clearStoredAccessToken = (): void => {
  window.localStorage.removeItem(AUTH_ACCESS_TOKEN_STORAGE_KEY);
};

const toAuthenticatedSession = (
  accessToken: string,
  payload: {
    user: AuthenticatedSession['user'];
    tenant: AuthenticatedSession['tenant'];
    session: AuthenticatedSession['session'];
  },
): AuthenticatedSession => ({
  accessToken,
  session: payload.session,
  tenant: payload.tenant,
  user: payload.user,
});

const isUnauthorizedAuthError = (error: AuthApiError): boolean => {
  if (error.status !== 401) {
    return false;
  }

  if (!error.code) {
    return true;
  }

  return AUTH_EXPIRED_CODES.has(error.code);
};

const getSessionExpiredNotice = (errorCode?: string): string => {
  if (errorCode && AUTH_EXPIRED_CODES.has(errorCode)) {
    return 'Session expired. Please sign in again.';
  }
  return 'Authentication required. Please sign in.';
};

type SessionFetchResult =
  | {
      ok: true;
      session: AuthenticatedSession;
    }
  | {
      ok: false;
      error: AuthApiError;
    };

export function AuthSessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(defaultState);

  const applyAuthenticated = useCallback((session: AuthenticatedSession) => {
    storeAccessToken(session.accessToken);
    setState({
      errorMessage: null,
      isWorking: false,
      notice: null,
      session,
      status: 'authenticated',
    });
  }, []);

  const applyUnauthenticated = useCallback((notice: string | null) => {
    clearStoredAccessToken();
    setState({
      errorMessage: null,
      isWorking: false,
      notice,
      session: null,
      status: 'unauthenticated',
    });
  }, []);

  const applyError = useCallback((message: string) => {
    setState({
      errorMessage: message,
      isWorking: false,
      notice: null,
      session: null,
      status: 'error',
    });
  }, []);

  const fetchSessionWithAccessToken = useCallback(
    async (accessToken: string): Promise<SessionFetchResult> => {
      const meResponse = await fetchMe(accessToken);
      if (!meResponse.ok) {
        return {
          ok: false,
          error: meResponse.error,
        };
      }

      return {
        ok: true,
        session: toAuthenticatedSession(accessToken, {
          session: meResponse.data.session,
          tenant: meResponse.data.tenant,
          user: meResponse.data.user,
        }),
      };
    },
    [],
  );

  const runRefreshFlow = useCallback(async (): Promise<AuthenticatedSession | null> => {
    const refreshResponse = await refreshAccessToken();
    if (!refreshResponse.ok) {
      applyUnauthenticated(getSessionExpiredNotice(refreshResponse.error.code));
      return null;
    }

    const refreshedAccessToken = refreshResponse.data.access_token;
    const sessionResult = await fetchSessionWithAccessToken(refreshedAccessToken);
    if (sessionResult.ok) {
      return sessionResult.session;
    }

    if (isUnauthorizedAuthError(sessionResult.error)) {
      applyUnauthenticated(getSessionExpiredNotice(sessionResult.error.code));
      return null;
    }

    applyError(sessionResult.error.message);
    return null;
  }, [applyError, applyUnauthenticated, fetchSessionWithAccessToken]);

  const loadSessionFromApi = useCallback(async (): Promise<void> => {
    const storedAccessToken = readStoredAccessToken();
    if (!storedAccessToken) {
      await Promise.resolve();
      applyUnauthenticated(null);
      return;
    }

    const sessionResult = await fetchSessionWithAccessToken(storedAccessToken);
    if (sessionResult.ok) {
      applyAuthenticated(sessionResult.session);
      return;
    }

    if (isUnauthorizedAuthError(sessionResult.error)) {
      const refreshedSession = await runRefreshFlow();
      if (refreshedSession) {
        applyAuthenticated(refreshedSession);
      }
      return;
    }

    applyError(sessionResult.error.message);
  }, [applyAuthenticated, applyError, applyUnauthenticated, fetchSessionWithAccessToken, runRefreshFlow]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadSessionFromApi();
    });
  }, [loadSessionFromApi]);

  const signIn = useCallback(
    async (payload: LoginRequest): Promise<AuthActionResult> => {
      setState((previous) => ({
        ...previous,
        errorMessage: null,
        isWorking: true,
        notice: null,
      }));

      const response = await loginWithPassword(payload);
      if (!response.ok) {
        applyUnauthenticated(null);
        return {
          ok: false,
          error: response.error,
        };
      }

      applyAuthenticated(
        toAuthenticatedSession(response.data.access_token, {
          session: response.data.session,
          tenant: response.data.tenant,
          user: response.data.user,
        }),
      );
      return { ok: true };
    },
    [applyAuthenticated, applyUnauthenticated],
  );

  const signOut = useCallback(async (): Promise<void> => {
    setState((previous) => ({
      ...previous,
      isWorking: true,
    }));

    await logoutSession();
    applyUnauthenticated('Signed out successfully.');
  }, [applyUnauthenticated]);

  const retry = useCallback(async (): Promise<void> => {
    setState((previous) => ({
      ...previous,
      errorMessage: null,
      status: 'checking',
    }));
    await loadSessionFromApi();
  }, [loadSessionFromApi]);

  const clearNotice = useCallback(() => {
    setState((previous) => ({
      ...previous,
      notice: null,
    }));
  }, []);

  const value = useMemo<AuthSessionContextValue>(
    () => ({
      ...state,
      clearNotice,
      retry,
      signIn,
      signOut,
    }),
    [clearNotice, retry, signIn, signOut, state],
  );

  return <AuthSessionContext.Provider value={value}>{children}</AuthSessionContext.Provider>;
}
