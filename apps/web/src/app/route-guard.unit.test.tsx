import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import App from '../App';
import { AUTH_STUB_STORAGE_KEY } from './authStub.constants';

describe('FE-003 app shell + protected route skeleton', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.pushState({}, '', '/');
  });

  it('redirects unauthenticated users to login when opening protected route', async () => {
    window.localStorage.setItem(AUTH_STUB_STORAGE_KEY, 'unauthenticated');
    window.history.pushState({}, '', '/dashboard');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Login' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign in (stub)' })).toBeInTheDocument();
  });

  it('renders shell layout and navigation for authenticated users', async () => {
    window.localStorage.setItem(AUTH_STUB_STORAGE_KEY, 'authenticated');
    window.history.pushState({}, '', '/dashboard');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Invoices Web' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page');
  });

  it('renders a safe fallback when auth stub state is invalid', async () => {
    window.localStorage.setItem(AUTH_STUB_STORAGE_KEY, 'broken-state');
    window.history.pushState({}, '', '/dashboard');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Session check failed' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry session check' })).toBeInTheDocument();
  });
});
