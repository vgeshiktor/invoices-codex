import { createContext, useContext } from 'react';
import type { AuthStubStatus } from './authStub.constants';

export interface AuthStubContextValue {
  status: AuthStubStatus;
  retry: () => void;
  signIn: () => void;
  signOut: () => void;
}

export const AuthStubContext = createContext<AuthStubContextValue | undefined>(undefined);

export const useAuthStub = (): AuthStubContextValue => {
  const context = useContext(AuthStubContext);
  if (!context) {
    throw new Error('useAuthStub must be used within AuthStubProvider');
  }
  return context;
};
