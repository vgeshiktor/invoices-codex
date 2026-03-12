import { useState } from 'react';
import { getDashboardSummary } from './features/dashboard/api/getDashboardSummary';
import { normalizeApiError, type ApiError } from './shared/api/client';
import type { DashboardSummaryV1DashboardSummaryGetResponse } from './shared/api/generated';
import { frontendEnv } from './shared/config/env';
import { safeJsonStringify } from './shared/utils/serialization';
import './App.css';

type ScreenState =
  | { mode: 'idle' }
  | { mode: 'loading' }
  | {
      mode: 'success';
      data: DashboardSummaryV1DashboardSummaryGetResponse | null;
    }
  | { mode: 'error'; error: ApiError };

function App() {
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
    <main className="app">
      <header className="app__header">
        <h1>Invoices Web</h1>
        <p>Day 1 FE-004 integration path: typed OpenAPI client + env-based base URL.</p>
      </header>

      <section className="app__meta">
        <div>
          <strong>Base URL:</strong> {frontendEnv.apiBaseUrl}
        </div>
        <div>
          <strong>Runtime:</strong> {frontendEnv.appEnv}
        </div>
      </section>

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
          <h2>Success</h2>
          <p>Dashboard summary fetched successfully.</p>
          <pre>{safeJsonStringify(state.data, { includeErrorStack })}</pre>
        </section>
      )}

      {state.mode === 'error' && (
        <section className="app__panel app__panel--error">
          <h2>Request failed</h2>
          <p>{state.error.message}</p>
          <p>
            {state.error.status ? `HTTP ${state.error.status}` : 'No HTTP response'}
            {state.error.requestId ? ` | request-id: ${state.error.requestId}` : ''}
          </p>
          <pre>{safeJsonStringify(state.error.cause, { includeErrorStack })}</pre>
        </section>
      )}
    </main>
  );
}

export default App;
