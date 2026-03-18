export type ProviderType = 'gmail' | 'outlook';

export type ProviderConnectionStatus = 'connected' | 'disconnected' | 'error';
export type ProviderConnectionTestStatus = 'success' | 'failure';

export interface ProviderSettingsItem {
  id: string;
  providerType: ProviderType;
  displayName: string;
  connectionStatus: ProviderConnectionStatus;
  lastErrorMessage: string | null;
  updatedAt: string;
  config: Record<string, unknown>;
}

export interface ProviderConnectionTestResult {
  provider: ProviderSettingsItem;
  status: ProviderConnectionTestStatus;
  message: string;
  testedAt: string;
  requestId: string | null;
}

export type ProviderAction = 'connect' | 'disconnect' | 'reauth' | 'testConnection';
