import { apiClient, normalizeApiError } from '../../../shared/api/client';
import { getRuntimeAuthHeaders } from '../../../shared/api/runtimeAuth';
import type { ProviderConnectionTestResult, ProviderSettingsAdapter, ProviderSettingsItem, ProviderType } from '../model/providerSettings';

type RawProviderResponse = {
  id: string;
  provider_type: ProviderType;
  display_name: string | null;
  connection_status: string;
  last_error_message: string | null;
  updated_at: string | null;
  config: Record<string, unknown>;
};

const parseProvider = (value: RawProviderResponse): ProviderSettingsItem | null => {
  if (!value || typeof value.id !== 'string' || typeof value.provider_type !== 'string') {
    return null;
  }
  return {
    id: value.id,
    providerType: value.provider_type,
    displayName: value.display_name || value.provider_type,
    connectionStatus: (value.connection_status as ProviderSettingsItem['connectionStatus']) ?? 'disconnected',
    lastErrorMessage: value.last_error_message ?? null,
    updatedAt: value.updated_at ?? new Date().toISOString(),
    config: value.config ?? {},
  } as ProviderSettingsItem;
};

const providerResponseToItem = (result: unknown): ProviderSettingsItem => {
  const parsed = parseProvider(result as RawProviderResponse);
  if (!parsed) {
    throw new Error('Provider response was malformed');
  }
  return parsed;
};

const buildEndpoint = (providerId: string) => `/v1/providers/${providerId}`;

const requestConfig = () => ({
  headers: getRuntimeAuthHeaders(),
});

const updateProvider = async (
  providerId: string,
  status: ProviderSettingsItem['connectionStatus'],
): Promise<ProviderSettingsItem> => {
  try {
    const result = await apiClient.patch<RawProviderResponse, unknown>({
      url: buildEndpoint(providerId),
      headers: {
        ...requestConfig().headers,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ connection_status: status }),
    });
    if (result.error) {
      throw await normalizeApiError(result.error, result.response);
    }
    return providerResponseToItem(result.data);
  } catch (error) {
    throw await normalizeApiError(error);
  }
};

export const providerSettingsAdapter: ProviderSettingsAdapter = {
  listProviders: async () => {
    try {
      const result = await apiClient.get<{ items: RawProviderResponse[] }>({
        url: '/v1/providers?limit=10&offset=0',
        headers: requestConfig().headers,
      });
      if (result.error) {
        throw await normalizeApiError(result.error, result.response);
      }
      return result.data.items.map(providerResponseToItem);
    } catch (error) {
      throw await normalizeApiError(error);
    }
  },
  connectProvider: async (provider) => updateProvider(provider.id, 'connected'),
  disconnectProvider: async (provider) => updateProvider(provider.id, 'disconnected'),
  reauthProvider: async (provider) => updateProvider(provider.id, 'connected'),
  testConnection: async (provider) => {
    try {
      const result = await apiClient.post<{ status: string; message: string; tested_at: string; request_id?: string }>({
        url: `${buildEndpoint(provider.id)}/test-connection`,
        headers: {
          ...requestConfig().headers,
          'Content-Type': 'application/json',
        },
      });
      if (result.error) {
        throw await normalizeApiError(result.error, result.response);
      }
      return {
        provider,
        status: result.data.status === 'success' ? 'success' : 'failure',
        message: result.data.message,
        testedAt: result.data.tested_at,
        requestId: result.data.request_id ?? null,
      };
    } catch (error) {
      throw await normalizeApiError(error);
    }
  },
};
