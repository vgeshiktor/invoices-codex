import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStub } from '../app/authStub.context';
import { RouteStatusPage } from '../pages/RouteStatusPage';

export function ProtectedRoute() {
  const { retry, status } = useAuthStub();

  if (status === 'error') {
    return (
      <RouteStatusPage
        actionLabel="Retry session check"
        message="Auth stub state is invalid. Fix local storage state or retry."
        onAction={retry}
        title="Session check failed"
      />
    );
  }

  if (status !== 'authenticated') {
    return <Navigate replace to="/login" />;
  }

  return <Outlet />;
}
