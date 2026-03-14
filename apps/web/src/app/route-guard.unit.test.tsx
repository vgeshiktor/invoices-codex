import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import App from '../App';
import { AUTH_ACCESS_TOKEN_STORAGE_KEY } from './authSession.constants';
import {
  AUTH_TEST_ACCESS_TOKEN,
  authLoginInvalidCredentialsHandler,
  authMeUnauthorizedExpiredHandler,
  authRefreshUnauthorizedHandler,
} from '../test/msw/handlers';
import { server } from '../test/msw/server';

describe('FE-101 auth flow and protected route behavior', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.pushState({}, '', '/');
  });

  it('redirects unauthenticated users to login when opening protected routes', async () => {
    window.history.pushState({}, '', '/dashboard');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Login' })).toBeInTheDocument();
    expect(
      screen.getByText('Sign in with your tenant credentials to open protected screens.'),
    ).toBeInTheDocument();
  });

  it('renders shell layout for authenticated sessions', async () => {
    window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, AUTH_TEST_ACCESS_TOKEN);
    window.history.pushState({}, '', '/dashboard');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Invoices Web' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByText(/ops@acme\.test/)).toBeInTheDocument();
  });

  it('shows session-expired UX and blocks protected route when token and refresh are unauthorized', async () => {
    server.use(authMeUnauthorizedExpiredHandler, authRefreshUnauthorizedHandler);
    window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, 'expired-token');
    window.history.pushState({}, '', '/dashboard');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Login' })).toBeInTheDocument();
    expect(screen.getByText('Session expired. Please sign in again.')).toBeInTheDocument();
  });

  it('keeps user on login and surfaces auth error when credentials are invalid', async () => {
    server.use(authLoginInvalidCredentialsHandler);
    const user = userEvent.setup();

    render(<App />);

    await screen.findByRole('heading', { name: 'Login' });
    await user.type(screen.getByLabelText('Tenant slug'), 'acme');
    await user.type(screen.getByLabelText('Email'), 'ops@acme.test');
    await user.type(screen.getByLabelText('Password'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.');
    expect(screen.getByRole('heading', { name: 'Login' })).toBeInTheDocument();
  });
});
