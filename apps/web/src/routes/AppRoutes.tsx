import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/shell/AppShell';
import { DashboardPage } from '../pages/DashboardPage';
import { CollectionRunDetailPage } from '../pages/CollectionRunDetailPage';
import { CollectionWizardPage } from '../pages/CollectionWizardPage';
import { ProviderSettingsScreen } from '../features/providers/components/ProviderSettingsScreen';
import { ReportCreationScreen } from '../features/reports/components/ReportCreationScreen';
import { ReportDetailScreen } from '../features/reports/components/ReportDetailScreen';
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
          <Route element={<ProviderSettingsScreen />} path="/providers" />
          <Route element={<CollectionWizardPage />} path="/collections" />
          <Route element={<CollectionRunDetailPage />} path="/collections/:collectionJobId" />
          <Route element={<ReportCreationScreen />} path="/reports" />
          <Route element={<ReportDetailScreen />} path="/reports/:reportId" />
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
