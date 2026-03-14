import type { ProviderSettingsItem, ProviderType } from '../model/providerSettings';

export interface ProviderSettingsAdapter {
  listProviders: () => Promise<ProviderSettingsItem[]>;
  connectProvider: (providerType: ProviderType) => Promise<ProviderSettingsItem>;
  disconnectProvider: (providerType: ProviderType) => Promise<ProviderSettingsItem>;
  reauthProvider: (providerType: ProviderType) => Promise<ProviderSettingsItem>;
}

const PROVIDER_ORDER: ProviderType[] = ['gmail', 'outlook'];

const toDisplayName = (providerType: ProviderType): string =>
  providerType === 'gmail' ? 'Gmail' : 'Outlook';

const nowIso = (): string => new Date().toISOString();

export const createDefaultProviderItems = (): ProviderSettingsItem[] =>
  PROVIDER_ORDER.map((providerType) => ({
    connectionStatus: 'disconnected',
    displayName: toDisplayName(providerType),
    id: `local-${providerType}`,
    lastErrorMessage: null,
    providerType,
    updatedAt: nowIso(),
  }));

const withUpdatedStatus = (
  provider: ProviderSettingsItem,
  connectionStatus: ProviderSettingsItem['connectionStatus'],
): ProviderSettingsItem => ({
  ...provider,
  connectionStatus,
  lastErrorMessage: connectionStatus === 'error' ? provider.lastErrorMessage : null,
  updatedAt: nowIso(),
});

const updateByProviderType = (
  providers: ProviderSettingsItem[],
  providerType: ProviderType,
  update: (provider: ProviderSettingsItem) => ProviderSettingsItem,
): ProviderSettingsItem[] =>
  providers.map((provider) => (provider.providerType === providerType ? update(provider) : provider));

const findByProviderType = (
  providers: ProviderSettingsItem[],
  providerType: ProviderType,
): ProviderSettingsItem => {
  const provider = providers.find((item) => item.providerType === providerType);
  if (!provider) {
    throw new Error(`Provider ${providerType} is not configured`);
  }
  return provider;
};

// BE-102 dependency:
// replace this local adapter with generated SDK calls once OAuth lifecycle
// endpoints are available in the OpenAPI snapshot.
export const createLocalProviderSettingsAdapter = (): ProviderSettingsAdapter => {
  let providers = createDefaultProviderItems();

  return {
    listProviders: async () => providers,
    connectProvider: async (providerType) => {
      providers = updateByProviderType(providers, providerType, (provider) =>
        withUpdatedStatus(provider, 'connected'),
      );
      return findByProviderType(providers, providerType);
    },
    disconnectProvider: async (providerType) => {
      providers = updateByProviderType(providers, providerType, (provider) =>
        withUpdatedStatus(provider, 'disconnected'),
      );
      return findByProviderType(providers, providerType);
    },
    reauthProvider: async (providerType) => {
      const provider = findByProviderType(providers, providerType);
      if (provider.connectionStatus === 'disconnected') {
        throw new Error(`${provider.displayName} must be connected before re-auth`);
      }
      providers = updateByProviderType(providers, providerType, (currentProvider) =>
        withUpdatedStatus(currentProvider, 'connected'),
      );
      return findByProviderType(providers, providerType);
    },
  };
};

export const providerSettingsAdapter = createLocalProviderSettingsAdapter();
