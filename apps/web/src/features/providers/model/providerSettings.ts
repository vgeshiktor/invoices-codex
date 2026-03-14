export type ProviderType = 'gmail' | 'outlook';

export type ProviderConnectionStatus = 'connected' | 'disconnected' | 'error';

export interface ProviderSettingsItem {
  id: string;
  providerType: ProviderType;
  displayName: string;
  connectionStatus: ProviderConnectionStatus;
  lastErrorMessage: string | null;
  updatedAt: string;
}

export type ProviderAction = 'connect' | 'disconnect' | 'reauth';
