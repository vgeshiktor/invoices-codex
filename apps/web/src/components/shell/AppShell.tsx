import { NavLink, Outlet } from 'react-router-dom';
import { useAuthStub } from '../../app/authStub.context';
import { frontendEnv } from '../../shared/config/env';

const navItems = [
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'Providers', to: '/providers' },
  { label: 'Collections', to: '/collections' },
  { label: 'Reports', to: '/reports' },
  { label: 'Settings', to: '/settings' },
];

export function AppShell() {
  const { signOut } = useAuthStub();

  return (
    <div className="shell">
      <header className="shell__header">
        <div>
          <h1 className="shell__title">Invoices Web</h1>
          <p className="shell__subtitle">App shell + protected route skeleton (FE-003)</p>
        </div>
        <button className="shell__button" onClick={signOut} type="button">
          Sign out
        </button>
      </header>

      <div className="shell__meta">
        <span>
          <strong>Base URL:</strong> {frontendEnv.apiBaseUrl}
        </span>
        <span>
          <strong>Runtime:</strong> {frontendEnv.appEnv}
        </span>
      </div>

      <div className="shell__layout">
        <nav aria-label="Primary" className="shell__nav">
          {navItems.map((item) => (
            <NavLink
              className={({ isActive }) =>
                isActive ? 'shell__nav-link shell__nav-link--active' : 'shell__nav-link'
              }
              key={item.to}
              to={item.to}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <main className="shell__content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
