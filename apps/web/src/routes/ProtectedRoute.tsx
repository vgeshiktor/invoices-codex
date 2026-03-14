import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthSession } from '../app/authSession.context';
import { RouteStatusPage } from '../pages/RouteStatusPage';

export function ProtectedRoute() {
  const location = useLocation();
  const { errorMessage, notice, retry, status } = useAuthSession();

  if (status === 'checking') {
    return (
      <main aria-busy="true" className="route-status">
        <h1>Checking session</h1>
        <p>Validating your login before opening protected content.</p>
      </main>
    );
  }

  if (status === 'error') {
    return (
      <RouteStatusPage
        actionLabel="Retry session check"
        message={errorMessage ?? 'Unable to verify your session right now.'}
        onAction={() => {
          void retry();
        }}
        title="Session check failed"
      />
    );
  }

  if (status === 'unauthenticated') {
    return (
      <Navigate
        replace
        state={{
          from: `${location.pathname}${location.search}`,
          reason: notice,
        }}
        to="/login"
      />
    );
  }

  return <Outlet />;
}
