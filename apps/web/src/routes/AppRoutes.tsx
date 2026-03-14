import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/shell/AppShell';
import { DashboardPage } from '../pages/DashboardPage';
import { LoginPage } from '../pages/LoginPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';
import { RouteStatusPage } from '../pages/RouteStatusPage';
import { ProtectedRoute } from './ProtectedRoute';

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<LoginPage />} path="/login" />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route element={<Navigate replace to="/dashboard" />} index />
          <Route element={<DashboardPage />} path="/dashboard" />
          <Route element={<PlaceholderPage title="Providers" />} path="/providers" />
          <Route element={<PlaceholderPage title="Collections" />} path="/collections" />
          <Route element={<PlaceholderPage title="Reports" />} path="/reports" />
          <Route element={<PlaceholderPage title="Settings" />} path="/settings" />
        </Route>
      </Route>

      <Route
        element={
          <RouteStatusPage
            message="Use navigation to continue."
            title="Page not found"
          />
        }
        path="*"
      />
    </Routes>
  );
}
