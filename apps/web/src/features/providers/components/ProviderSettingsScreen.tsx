import { useCallback, useEffect, useState } from 'react';
import { normalizeApiError, type ApiError } from '../../../shared/api/client';
import { frontendEnv } from '../../../shared/config/env';
import {
  createDefaultProviderItems,
  providerSettingsAdapter,
  type ProviderSettingsAdapter,
} from '../api/providerSettingsAdapter';
import type {
  ProviderAction,
  ProviderConnectionTestResult,
  ProviderConnectionTestStatus,
  ProviderSettingsItem,
  ProviderType,
} from '../model/providerSettings';

const connectionLabel: Record<ProviderSettingsItem['connectionStatus'], string> = {
  connected: 'Connected',
  disconnected: 'Disconnected',
  error: 'Error',
};

const testStatusLabel: Record<ProviderConnectionTestStatus, string> = {
  failure: 'Failure',
  success: 'Success',
};

const actionLabel: Record<ProviderAction, string> = {
  connect: 'Connect',
  disconnect: 'Disconnect',
  reauth: 'Re-auth',
  testConnection: 'Test connection',
};

const pendingActionLabel: Record<ProviderAction, string> = {
  connect: 'Connecting...',
  disconnect: 'Disconnecting...',
  reauth: 'Re-authorizing...',
  testConnection: 'Testing...',
};

const upsertProvider = (
  providers: ProviderSettingsItem[],
  updatedProvider: ProviderSettingsItem,
): ProviderSettingsItem[] => {
  const existingProviderIndex = providers.findIndex(
    (provider) => provider.providerType === updatedProvider.providerType,
  );

  if (existingProviderIndex === -1) {
    return [...providers, updatedProvider];
  }

  return providers.map((provider) =>
    provider.providerType === updatedProvider.providerType ? updatedProvider : provider,
  );
};

const toSortedProviders = (providers: ProviderSettingsItem[]): ProviderSettingsItem[] =>
  [...providers].sort((left, right) => left.providerType.localeCompare(right.providerType));

const mergeWithDefaultProviders = (
  providers: ProviderSettingsItem[],
): ProviderSettingsItem[] => {
  const providersByType = new Map(providers.map((provider) => [provider.providerType, provider]));
  return createDefaultProviderItems().map(
    (defaultProvider) => providersByType.get(defaultProvider.providerType) ?? defaultProvider,
  );
};

interface ProviderSettingsScreenProps {
  adapter?: ProviderSettingsAdapter;
}

type LoadState = 'loading' | 'ready' | 'error';

export function ProviderSettingsScreen({
  adapter = providerSettingsAdapter,
}: ProviderSettingsScreenProps) {
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [providers, setProviders] = useState<ProviderSettingsItem[]>(createDefaultProviderItems);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [actionError, setActionError] = useState<ApiError | null>(null);
  const [testResults, setTestResults] = useState<
    Partial<Record<ProviderType, ProviderConnectionTestResult>>
  >({});
  const [pendingActions, setPendingActions] = useState<Partial<Record<ProviderType, ProviderAction>>>(
    {},
  );

  const loadProviders = useCallback(async () => {
    setLoadState('loading');
    setLoadError(null);

    try {
      const response = await adapter.listProviders();
      setProviders(toSortedProviders(mergeWithDefaultProviders(response)));
      setTestResults({});
      setLoadState('ready');
    } catch (error) {
      setLoadError(await normalizeApiError(error));
      setLoadState('error');
    }
  }, [adapter]);

  useEffect(() => {
    void loadProviders();
  }, [loadProviders]);

  const runProviderAction = async (providerType: ProviderType, action: ProviderAction) => {
    setActionError(null);
    setPendingActions((currentPendingActions) => ({ ...currentPendingActions, [providerType]: action }));

    try {
      if (action === 'testConnection') {
        const result = await adapter.testProviderConnection(providerType);
        setProviders((currentProviders) =>
          toSortedProviders(upsertProvider(currentProviders, result.provider)),
        );
        setTestResults((currentResults) => ({ ...currentResults, [providerType]: result }));
        return;
      }

      let updatedProvider: ProviderSettingsItem;
      if (action === 'connect') {
        updatedProvider = await adapter.connectProvider(providerType);
      } else if (action === 'disconnect') {
        updatedProvider = await adapter.disconnectProvider(providerType);
      } else {
        updatedProvider = await adapter.reauthProvider(providerType);
      }

      setProviders((currentProviders) =>
        toSortedProviders(upsertProvider(currentProviders, updatedProvider)),
      );
    } catch (error) {
      setActionError(await normalizeApiError(error));
    } finally {
      setPendingActions((currentPendingActions) => {
        const nextPendingActions = { ...currentPendingActions };
        delete nextPendingActions[providerType];
        return nextPendingActions;
      });
    }
  };

  return (
    <section className="app">
      <header className="app__header">
        <h2>Provider settings</h2>
        <p>Connect and manage Gmail or Outlook mailbox access for invoice collection.</p>
      </header>

      <section className="app__meta">
        <div>
          <strong>Base URL:</strong> {frontendEnv.apiBaseUrl}
        </div>
        <div>
          <strong>Runtime:</strong> {frontendEnv.appEnv}
        </div>
      </section>

      {loadState === 'loading' && (
        <section aria-live="polite" className="app__panel">
          <h2>Loading providers</h2>
          <p>Fetching provider configuration...</p>
        </section>
      )}

      {loadState === 'error' && loadError && (
        <section className="app__panel app__panel--error">
          <h2>Could not load provider settings</h2>
          <p>{loadError.message}</p>
          <button className="app__button" onClick={loadProviders} type="button">
            Retry
          </button>
        </section>
      )}

      {loadState === 'ready' && (
        <>
          {actionError && (
            <section className="app__panel app__panel--error" role="alert">
              <h2>Action failed</h2>
              <p>{actionError.message}</p>
            </section>
          )}

          <section className="provider-grid">
            {providers.map((provider) => {
              const pendingAction = pendingActions[provider.providerType];
              const isBusy = pendingAction !== undefined;
              const testResult = testResults[provider.providerType];

              return (
                <article
                  className="provider-card"
                  data-testid={`provider-card-${provider.providerType}`}
                  key={provider.providerType}
                >
                  <header className="provider-card__header">
                    <h2>{provider.displayName}</h2>
                    <span className={`status-badge status-badge--${provider.connectionStatus}`}>
                      {connectionLabel[provider.connectionStatus]}
                    </span>
                  </header>

                  <p className="provider-card__meta">
                    Last updated: {new Date(provider.updatedAt).toLocaleString()}
                  </p>

                  {provider.lastErrorMessage && (
                    <p className="provider-card__error">{provider.lastErrorMessage}</p>
                  )}

                  <div className="provider-card__actions">
                    <button
                      className="app__button"
                      disabled={isBusy}
                      onClick={() => {
                        void runProviderAction(provider.providerType, 'testConnection');
                      }}
                      type="button"
                    >
                      {pendingAction === 'testConnection'
                        ? pendingActionLabel.testConnection
                        : actionLabel.testConnection}
                    </button>

                    {provider.connectionStatus === 'disconnected' && (
                      <button
                        className="app__button"
                        disabled={isBusy}
                        onClick={() => {
                          void runProviderAction(provider.providerType, 'connect');
                        }}
                        type="button"
                      >
                        {pendingAction === 'connect'
                          ? pendingActionLabel.connect
                          : actionLabel.connect}
                      </button>
                    )}

                    {provider.connectionStatus !== 'disconnected' && (
                      <>
                        <button
                          className="app__button"
                          disabled={isBusy}
                          onClick={() => {
                            void runProviderAction(provider.providerType, 'reauth');
                          }}
                          type="button"
                        >
                          {pendingAction === 'reauth'
                            ? pendingActionLabel.reauth
                            : actionLabel.reauth}
                        </button>
                        <button
                          className="app__button app__button--danger"
                          disabled={isBusy}
                          onClick={() => {
                            void runProviderAction(provider.providerType, 'disconnect');
                          }}
                          type="button"
                        >
                          {pendingAction === 'disconnect'
                            ? pendingActionLabel.disconnect
                            : actionLabel.disconnect}
                        </button>
                      </>
                    )}
                  </div>

                  {testResult && (
                    <section
                      aria-live="polite"
                      className={
                        testResult.status === 'failure' ? 'app__panel app__panel--error' : 'app__panel'
                      }
                      data-testid={`provider-test-result-${provider.providerType}`}
                    >
                      <p>
                        <strong>Last test:</strong> {testStatusLabel[testResult.status]}
                      </p>
                      <p>{testResult.message}</p>
                      <p>Tested at: {new Date(testResult.testedAt).toLocaleString()}</p>
                      {testResult.requestId && <p>request-id: {testResult.requestId}</p>}
                    </section>
                  )}
                </article>
              );
            })}
          </section>
        </>
      )}
    </section>
  );
}
