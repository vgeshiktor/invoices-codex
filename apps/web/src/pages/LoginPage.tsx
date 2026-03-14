import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthSession } from '../app/authSession.context';

interface LoginLocationState {
  from?: string;
  reason?: string | null;
}

interface LoginFormState {
  tenantSlug: string;
  email: string;
  password: string;
}

const INITIAL_FORM_STATE: LoginFormState = {
  email: '',
  password: '',
  tenantSlug: '',
};

const sanitizeRedirectTarget = (rawTarget: string | undefined): string => {
  if (!rawTarget || rawTarget === '/login') {
    return '/dashboard';
  }
  return rawTarget;
};

export function LoginPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { clearNotice, isWorking, notice, signIn, status } = useAuthSession();
  const [form, setForm] = useState<LoginFormState>(INITIAL_FORM_STATE);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const locationState = (location.state ?? null) as LoginLocationState | null;
  const redirectTarget = sanitizeRedirectTarget(locationState?.from);

  const noticeMessage = useMemo(() => {
    if (locationState?.reason) {
      return locationState.reason;
    }
    return notice;
  }, [locationState?.reason, notice]);

  useEffect(() => {
    if (status === 'authenticated') {
      navigate(redirectTarget, { replace: true });
    }
  }, [navigate, redirectTarget, status]);

  useEffect(() => {
    if (!locationState?.reason) {
      return;
    }

    return () => {
      clearNotice();
    };
  }, [clearNotice, locationState?.reason]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    const result = await signIn({
      email: form.email.trim(),
      password: form.password,
      tenant_slug: form.tenantSlug.trim().toLowerCase(),
    });

    if (!result.ok) {
      setErrorMessage(result.error.message);
      return;
    }

    navigate(redirectTarget, { replace: true });
  };

  return (
    <main className="route-status">
      <h1>Login</h1>
      <p>Sign in with your tenant credentials to open protected screens.</p>

      {noticeMessage ? (
        <p className="auth-form__notice" role="status">
          {noticeMessage}
        </p>
      ) : null}

      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="auth-form__field" htmlFor="tenantSlug">
          Tenant slug
          <input
            autoComplete="organization"
            id="tenantSlug"
            name="tenantSlug"
            onChange={(event) => {
              setForm((current) => ({
                ...current,
                tenantSlug: event.target.value,
              }));
            }}
            placeholder="acme"
            required
            type="text"
            value={form.tenantSlug}
          />
        </label>

        <label className="auth-form__field" htmlFor="email">
          Email
          <input
            autoComplete="email"
            id="email"
            name="email"
            onChange={(event) => {
              setForm((current) => ({
                ...current,
                email: event.target.value,
              }));
            }}
            placeholder="ops@acme.test"
            required
            type="email"
            value={form.email}
          />
        </label>

        <label className="auth-form__field" htmlFor="password">
          Password
          <input
            autoComplete="current-password"
            id="password"
            name="password"
            onChange={(event) => {
              setForm((current) => ({
                ...current,
                password: event.target.value,
              }));
            }}
            required
            type="password"
            value={form.password}
          />
        </label>

        {errorMessage ? (
          <p className="auth-form__error" role="alert">
            {errorMessage}
          </p>
        ) : null}

        <button className="shell__button" disabled={isWorking} type="submit">
          {isWorking ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </main>
  );
}
