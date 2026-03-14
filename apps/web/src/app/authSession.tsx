import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
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

export function AuthSessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(defaultState);
  const isMountedRef = useRef(true);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const setSafeState = useCallback((nextState: AuthState) => {
    if (!isMountedRef.current) {
      return;
    }
    setState(nextState);
  }, []);

  const applyAuthenticated = useCallback(
    (session: AuthenticatedSession) => {
      storeAccessToken(session.accessToken);
      setSafeState({
        errorMessage: null,
        isWorking: false,
        notice: null,
        session,
        status: 'authenticated',
      });
    },
    [setSafeState],
  );

  const applyUnauthenticated = useCallback(
    (notice: string | null) => {
      clearStoredAccessToken();
      setSafeState({
        errorMessage: null,
        isWorking: false,
        notice,
        session: null,
        status: 'unauthenticated',
      });
    },
    [setSafeState],
  );

  const applyError = useCallback(
    (message: string) => {
      setSafeState({
        errorMessage: message,
        isWorking: false,
        notice: null,
        session: null,
        status: 'error',
      });
    },
    [setSafeState],
  );

  const loadSessionFromApi = useCallback(async (): Promise<void> => {
    const storedAccessToken = readStoredAccessToken();
    if (!storedAccessToken) {
      applyUnauthenticated(null);
      return;
    }

    const meResponse = await fetchMe(storedAccessToken);
    if (meResponse.ok) {
      applyAuthenticated(
        toAuthenticatedSession(storedAccessToken, {
          session: meResponse.data.session,
          tenant: meResponse.data.tenant,
          user: meResponse.data.user,
        }),
      );
      return;
    }

    if (isUnauthorizedAuthError(meResponse.error)) {
      const refreshResponse = await refreshAccessToken();
      if (!refreshResponse.ok) {
        applyUnauthenticated(getSessionExpiredNotice(refreshResponse.error.code));
        return;
      }

      const refreshedAccessToken = refreshResponse.data.access_token;
      const refreshedMeResponse = await fetchMe(refreshedAccessToken);
      if (!refreshedMeResponse.ok) {
        if (isUnauthorizedAuthError(refreshedMeResponse.error)) {
          applyUnauthenticated(getSessionExpiredNotice(refreshedMeResponse.error.code));
          return;
        }

        applyError(refreshedMeResponse.error.message);
        return;
      }

      applyAuthenticated(
        toAuthenticatedSession(refreshedAccessToken, {
          session: refreshedMeResponse.data.session,
          tenant: refreshedMeResponse.data.tenant,
          user: refreshedMeResponse.data.user,
        }),
      );
      return;
    }

    applyError(meResponse.error.message);
  }, [applyAuthenticated, applyError, applyUnauthenticated]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadSessionFromApi();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
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
