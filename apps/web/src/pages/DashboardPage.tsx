import { useState } from 'react';
import { getDashboardSummary } from '../features/dashboard/api/getDashboardSummary';
import { normalizeApiError, type ApiError } from '../shared/api/client';
import type { DashboardSummaryV1DashboardSummaryGetResponse } from '../shared/api/generated';
import { frontendEnv } from '../shared/config/env';
import { safeJsonStringify } from '../shared/utils/serialization';

type ScreenState =
  | { mode: 'idle' }
  | { mode: 'loading' }
  | {
      mode: 'success';
      data: DashboardSummaryV1DashboardSummaryGetResponse | null;
    }
  | { mode: 'error'; error: ApiError };

export function DashboardPage() {
  const [state, setState] = useState<ScreenState>({ mode: 'idle' });
  const includeErrorStack = frontendEnv.appEnv !== 'production';

  const loadDashboardSummary = async () => {
    setState({ mode: 'loading' });
    try {
      const response = await getDashboardSummary();

      if (!response.ok) {
        setState({
          mode: 'error',
          error: response.error,
        });
        return;
      }

      setState({
        mode: 'success',
        data: response.data,
      });
    } catch (error) {
      setState({
        mode: 'error',
        error: await normalizeApiError(error),
      });
    }
  };

  return (
    <section className="app">
      <header className="app__header">
        <h2>Dashboard</h2>
        <p>Typed OpenAPI client + env-based base URL are active on this page.</p>
      </header>

      <section className="app__actions">
        <button
          className="app__button"
          disabled={state.mode === 'loading'}
          onClick={loadDashboardSummary}
          type="button"
        >
          {state.mode === 'loading' ? 'Loading...' : 'Fetch dashboard summary'}
        </button>
      </section>

      {state.mode === 'success' && (
        <section className="app__panel">
          <h3>Success</h3>
          <p>Dashboard summary fetched successfully.</p>
          <pre>{safeJsonStringify(state.data, { includeErrorStack })}</pre>
        </section>
      )}

      {state.mode === 'error' && (
        <section className="app__panel app__panel--error">
          <h3>Request failed</h3>
          <p>{state.error.message}</p>
          <p>
            {state.error.status ? `HTTP ${state.error.status}` : 'No HTTP response'}
            {state.error.requestId ? ` | request-id: ${state.error.requestId}` : ''}
          </p>
          <pre>{safeJsonStringify(state.error.cause, { includeErrorStack })}</pre>
        </section>
      )}
    </section>
  );
}
