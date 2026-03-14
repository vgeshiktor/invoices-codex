import { useState, type ReactNode } from 'react';
import { AuthStubContext, type AuthStubContextValue } from './authStub.context';
import { AUTH_STUB_STORAGE_KEY, type AuthStubStatus } from './authStub.constants';

const resolveStoredStatus = (): AuthStubStatus => {
  const raw = window.localStorage.getItem(AUTH_STUB_STORAGE_KEY);

  if (raw === null || raw === 'unauthenticated') {
    return 'unauthenticated';
  }

  if (raw === 'authenticated') {
    return 'authenticated';
  }

  return 'error';
};

export function AuthStubProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStubStatus>(resolveStoredStatus);

  const retry = () => {
    setStatus(resolveStoredStatus());
  };

  const signIn = () => {
    window.localStorage.setItem(AUTH_STUB_STORAGE_KEY, 'authenticated');
    setStatus('authenticated');
  };

  const signOut = () => {
    window.localStorage.setItem(AUTH_STUB_STORAGE_KEY, 'unauthenticated');
    setStatus('unauthenticated');
  };

  const value: AuthStubContextValue = { status, retry, signIn, signOut };

  return <AuthStubContext.Provider value={value}>{children}</AuthStubContext.Provider>;
}
