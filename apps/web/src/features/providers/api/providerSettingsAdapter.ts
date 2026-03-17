import { AUTH_ACCESS_TOKEN_STORAGE_KEY } from '../../../app/authSession.constants';
import { normalizeApiError } from '../../../shared/api/client';
import { frontendEnv } from '../../../shared/config/env';
import type {
  ProviderConnectionTestResult,
  ProviderConnectionTestStatus,
  ProviderSettingsItem,
  ProviderType,
} from '../model/providerSettings';

export interface ProviderSettingsAdapter {
  listProviders: () => Promise<ProviderSettingsItem[]>;
  connectProvider: (providerType: ProviderType) => Promise<ProviderSettingsItem>;
  disconnectProvider: (providerType: ProviderType) => Promise<ProviderSettingsItem>;
  reauthProvider: (providerType: ProviderType) => Promise<ProviderSettingsItem>;
  testProviderConnection: (providerType: ProviderType) => Promise<ProviderConnectionTestResult>;
}

interface ProviderApiItem {
  id: string;
  provider_type: ProviderType;
  display_name: string;
  connection_status: ProviderSettingsItem['connectionStatus'];
  last_error_message: string | null;
  updated_at: string;
}

interface ProviderListResponse {
  items?: ProviderApiItem[];
}

interface ProviderOAuthStartResponse {
  provider: ProviderApiItem;
  authorization_url?: string;
}

interface ProviderConnectionTestApiResponse {
  provider: ProviderApiItem;
  status: ProviderConnectionTestStatus;
  message: string;
  tested_at: string;
  request_id?: string | null;
}

const PROVIDER_ORDER: ProviderType[] = ['gmail', 'outlook'];

const toDisplayName = (providerType: ProviderType): string =>
  providerType === 'gmail' ? 'Gmail' : 'Outlook';

const nowIso = (): string => new Date().toISOString();

const cloneProvider = (provider: ProviderSettingsItem): ProviderSettingsItem => ({
  ...provider,
});

export const createDefaultProviderItems = (): ProviderSettingsItem[] =>
  PROVIDER_ORDER.map((providerType) => ({
    connectionStatus: 'disconnected',
    displayName: toDisplayName(providerType),
    id: `local-${providerType}`,
    lastErrorMessage: null,
    providerType,
    updatedAt: nowIso(),
  }));

const readStoredAccessToken = (): string | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  const raw = window.localStorage.getItem(AUTH_ACCESS_TOKEN_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  const value = raw.trim();
  return value.length > 0 ? value : null;
};

const getRuntimeAuthHeaders = (): Record<string, string> | undefined => {
  const accessToken = readStoredAccessToken();
  if (accessToken) {
    return {
      Authorization: `Bearer ${accessToken}`,
    };
  }

  if (frontendEnv.apiKey) {
    return {
      'X-API-Key': frontendEnv.apiKey,
    };
  }

  return undefined;
};

const mapProvider = (provider: ProviderApiItem): ProviderSettingsItem => ({
  connectionStatus: provider.connection_status,
  displayName: provider.display_name,
  id: provider.id,
  lastErrorMessage: provider.last_error_message,
  providerType: provider.provider_type,
  updatedAt: provider.updated_at,
});

const isProviderApiItem = (value: unknown): value is ProviderApiItem => {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const record = value as Record<string, unknown>;
  return (
    typeof record.id === 'string' &&
    (record.provider_type === 'gmail' || record.provider_type === 'outlook') &&
    typeof record.display_name === 'string' &&
    (record.connection_status === 'connected' ||
      record.connection_status === 'disconnected' ||
      record.connection_status === 'error') &&
    typeof record.updated_at === 'string'
  );
};

const parseProviderList = (value: unknown): ProviderSettingsItem[] => {
  if (!value || typeof value !== 'object') {
    return [];
  }

  const items = (value as ProviderListResponse).items;
  if (!Array.isArray(items)) {
    return [];
  }

  return items.filter(isProviderApiItem).map((item) => mapProvider(item));
};

const parseProviderItem = (value: unknown): ProviderSettingsItem => {
  if (isProviderApiItem(value)) {
    return mapProvider(value);
  }

  if (
    value &&
    typeof value === 'object' &&
    'provider' in value &&
    isProviderApiItem((value as ProviderOAuthStartResponse).provider)
  ) {
    return mapProvider((value as ProviderOAuthStartResponse).provider);
  }

  throw new Error('Malformed provider response from API');
};

const isProviderConnectionTestStatus = (
  value: unknown,
): value is ProviderConnectionTestStatus => value === 'success' || value === 'failure';

const parseProviderConnectionTestResult = (value: unknown): ProviderConnectionTestResult => {
  if (!value || typeof value !== 'object') {
    throw new Error('Malformed provider test response from API');
  }

  const record = value as ProviderConnectionTestApiResponse;
  if (
    !isProviderApiItem(record.provider) ||
    !isProviderConnectionTestStatus(record.status) ||
    typeof record.message !== 'string' ||
    typeof record.tested_at !== 'string'
  ) {
    throw new Error('Malformed provider test response from API');
  }

  return {
    message: record.message,
    provider: mapProvider(record.provider),
    requestId: typeof record.request_id === 'string' ? record.request_id : null,
    status: record.status,
    testedAt: record.tested_at,
  };
};

const buildRedirectUri = (): string => {
  if (typeof window === 'undefined') {
    return 'http://127.0.0.1:4173/providers';
  }
  return `${window.location.origin}/providers`;
};

const sortProviders = (providers: ProviderSettingsItem[]): ProviderSettingsItem[] =>
  [...providers].sort((left, right) => left.providerType.localeCompare(right.providerType));

const findProviderByType = (
  providers: ProviderSettingsItem[],
  providerType: ProviderType,
): ProviderSettingsItem => {
  const provider = providers.find((item) => item.providerType === providerType);
  if (!provider) {
    throw new Error(`Provider ${providerType} is not configured`);
  }
  return provider;
};

type FetchImpl = typeof fetch;

interface LiveAdapterOptions {
  apiBaseUrl?: string;
  fetchImpl?: FetchImpl;
}

export const createProviderSettingsApiAdapter = (
  options: LiveAdapterOptions = {},
): ProviderSettingsAdapter => {
  const apiBaseUrl = options.apiBaseUrl ?? frontendEnv.apiBaseUrl;
  const fetchImpl = options.fetchImpl ?? fetch;

  const requestJson = async (
    path: string,
    init?: RequestInit,
  ): Promise<unknown> => {
    const response = await fetchImpl(`${apiBaseUrl}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        ...(getRuntimeAuthHeaders() ?? {}),
        ...(init?.headers ?? {}),
      },
    });

    let body: unknown = undefined;
    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('application/json') || contentType.includes('+json')) {
      body = await response.json();
    }

    if (!response.ok) {
      const apiError = await normalizeApiError(new Error('Provider request failed'), response);
      throw new Error(apiError.message);
    }

    return body;
  };

  const listProviderItems = async (): Promise<ProviderSettingsItem[]> => {
    const response = await requestJson('/v1/providers?limit=10&offset=0', {
      method: 'GET',
    });

    return sortProviders(parseProviderList(response));
  };

  const getProviderId = async (providerType: ProviderType): Promise<string> => {
    const providers = await listProviderItems();
    return findProviderByType(providers, providerType).id;
  };

  return {
    listProviders: listProviderItems,
    connectProvider: async (providerType) => {
      const providerId = await getProviderId(providerType);
      const response = await requestJson(`/v1/providers/${encodeURIComponent(providerId)}/oauth/start`, {
        body: JSON.stringify({
          redirect_uri: buildRedirectUri(),
        }),
        headers: {
          'Content-Type': 'application/json',
        },
        method: 'POST',
      });

      return parseProviderItem(response);
    },
    disconnectProvider: async (providerType) => {
      const providerId = await getProviderId(providerType);
      const response = await requestJson(`/v1/providers/${encodeURIComponent(providerId)}/oauth/revoke`, {
        method: 'POST',
      });

      return parseProviderItem(response);
    },
    reauthProvider: async (providerType) => {
      const providerId = await getProviderId(providerType);
      const response = await requestJson(`/v1/providers/${encodeURIComponent(providerId)}/oauth/refresh`, {
        method: 'POST',
      });

      return parseProviderItem(response);
    },
    testProviderConnection: async (providerType) => {
      const providerId = await getProviderId(providerType);
      const response = await requestJson(
        `/v1/providers/${encodeURIComponent(providerId)}/test-connection`,
        {
          method: 'POST',
        },
      );

      return parseProviderConnectionTestResult(response);
    },
  };
};

export const createLocalProviderSettingsAdapter = (): ProviderSettingsAdapter => {
  let providers = createDefaultProviderItems();

  return {
    listProviders: async () => providers.map(cloneProvider),
    connectProvider: async (providerType) => {
      providers = providers.map((provider) =>
        provider.providerType === providerType
          ? {
              ...provider,
              connectionStatus: 'connected',
              lastErrorMessage: null,
              updatedAt: nowIso(),
            }
          : provider,
      );
      return cloneProvider(findProviderByType(providers, providerType));
    },
    disconnectProvider: async (providerType) => {
      providers = providers.map((provider) =>
        provider.providerType === providerType
          ? {
              ...provider,
              connectionStatus: 'disconnected',
              lastErrorMessage: null,
              updatedAt: nowIso(),
            }
          : provider,
      );
      return cloneProvider(findProviderByType(providers, providerType));
    },
    reauthProvider: async (providerType) => {
      const provider = findProviderByType(providers, providerType);
      if (provider.connectionStatus === 'disconnected') {
        throw new Error(`${provider.displayName} must be connected before re-auth`);
      }
      providers = providers.map((currentProvider) =>
        currentProvider.providerType === providerType
          ? {
              ...currentProvider,
              connectionStatus: 'connected',
              lastErrorMessage: null,
              updatedAt: nowIso(),
            }
          : currentProvider,
      );
      return cloneProvider(findProviderByType(providers, providerType));
    },
    testProviderConnection: async (providerType) => {
      const provider = findProviderByType(providers, providerType);
      const testedAt = nowIso();

      if (provider.connectionStatus === 'disconnected') {
        providers = providers.map((currentProvider) =>
          currentProvider.providerType === providerType
            ? {
                ...currentProvider,
                lastErrorMessage: 'provider is not connected',
                updatedAt: testedAt,
              }
            : currentProvider,
        );
        return {
          message: 'provider is not connected',
          provider: cloneProvider(findProviderByType(providers, providerType)),
          requestId: null,
          status: 'failure',
          testedAt,
        };
      }

      providers = providers.map((currentProvider) =>
        currentProvider.providerType === providerType
          ? {
              ...currentProvider,
              connectionStatus: 'connected',
              lastErrorMessage: null,
              updatedAt: testedAt,
            }
          : currentProvider,
      );
      return {
        message: 'provider connection verified',
        provider: cloneProvider(findProviderByType(providers, providerType)),
        requestId: null,
        status: 'success',
        testedAt,
      };
    },
  };
};

export const providerSettingsAdapter = createProviderSettingsApiAdapter();
