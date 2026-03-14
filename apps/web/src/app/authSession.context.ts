import { createContext, useContext } from 'react';
import type {
  AuthApiError,
  AuthSessionMetadata,
  AuthTenant,
  AuthUser,
  LoginRequest,
} from '../features/auth/api/authApi';
import type { AuthSessionStatus } from './authSession.constants';

export interface AuthenticatedSession {
  accessToken: string;
  session: AuthSessionMetadata;
  tenant: AuthTenant;
  user: AuthUser;
}

export interface AuthState {
  status: AuthSessionStatus;
  session: AuthenticatedSession | null;
  notice: string | null;
  errorMessage: string | null;
  isWorking: boolean;
}

export type AuthActionResult =
  | {
      ok: true;
    }
  | {
      ok: false;
      error: AuthApiError;
    };

export interface AuthSessionContextValue extends AuthState {
  clearNotice: () => void;
  retry: () => Promise<void>;
  signIn: (payload: LoginRequest) => Promise<AuthActionResult>;
  signOut: () => Promise<void>;
}

export const AuthSessionContext = createContext<AuthSessionContextValue | undefined>(undefined);

export const useAuthSession = (): AuthSessionContextValue => {
  const context = useContext(AuthSessionContext);
  if (!context) {
    throw new Error('useAuthSession must be used within AuthSessionProvider');
  }
  return context;
};
