import { useState } from 'react';
import { getDashboardSummary } from './features/dashboard/api/getDashboardSummary';
import type { ApiError } from './shared/api/client';
import type { DashboardSummaryV1DashboardSummaryGetResponse } from './shared/api/generated';
import { frontendEnv } from './shared/config/env';
import './App.css';

type ScreenState =
  | { mode: 'idle' }
  | { mode: 'loading' }
  | {
      mode: 'success';
      data: DashboardSummaryV1DashboardSummaryGetResponse | null;
      requestId?: string;
      status: number;
    }
  | { mode: 'error'; error: ApiError; requestId?: string; status?: number };

const toJson = (value: unknown): string => JSON.stringify(value, null, 2);

function App() {
  const [state, setState] = useState<ScreenState>({ mode: 'idle' });

  const loadDashboardSummary = async () => {
    setState({ mode: 'loading' });
    const response = await getDashboardSummary();

    if ('error' in response) {
      setState({
        mode: 'error',
        error: response.error,
        requestId: response.requestId,
        status: response.status,
      });
      return;
    }

    setState({
      mode: 'success',
      data: response.data,
      requestId: response.requestId,
      status: response.status,
    });
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
          <p>
            HTTP {state.status}
            {state.requestId ? ` | request-id: ${state.requestId}` : ''}
          </p>
          <pre>{toJson(state.data)}</pre>
        </section>
      )}

      {state.mode === 'error' && (
        <section className="app__panel app__panel--error">
          <h2>Request failed</h2>
          <p>{state.error.message}</p>
          <p>
            {state.status ? `HTTP ${state.status}` : 'No HTTP response'}
            {state.requestId ? ` | request-id: ${state.requestId}` : ''}
          </p>
          <pre>{toJson(state.error.cause)}</pre>
        </section>
      )}
    </main>
  );
}

export default App;
