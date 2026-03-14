import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ProviderSettingsScreen } from './ProviderSettingsScreen';
import type { ProviderSettingsAdapter } from '../api/providerSettingsAdapter';
import type {
  ProviderConnectionStatus,
  ProviderSettingsItem,
  ProviderType,
} from '../model/providerSettings';

const createProvider = (
  providerType: ProviderType,
  connectionStatus: ProviderConnectionStatus,
): ProviderSettingsItem => ({
  connectionStatus,
  displayName: providerType === 'gmail' ? 'Gmail' : 'Outlook',
  id: `provider-${providerType}`,
  lastErrorMessage: null,
  providerType,
  updatedAt: '2026-03-14T00:00:00.000Z',
});

const buildAdapter = (
  providers: ProviderSettingsItem[],
  overrides?: Partial<{
    connectProvider: ProviderSettingsAdapter['connectProvider'];
    disconnectProvider: ProviderSettingsAdapter['disconnectProvider'];
    listProviders: ProviderSettingsAdapter['listProviders'];
    reauthProvider: ProviderSettingsAdapter['reauthProvider'];
  }>,
): ProviderSettingsAdapter => ({
  connectProvider:
    overrides?.connectProvider ??
    (async (providerType: ProviderType) => createProvider(providerType, 'connected')),
  disconnectProvider:
    overrides?.disconnectProvider ??
    (async (providerType: ProviderType) => createProvider(providerType, 'disconnected')),
  listProviders: overrides?.listProviders ?? (async () => providers),
  reauthProvider:
    overrides?.reauthProvider ??
    (async (providerType: ProviderType) => createProvider(providerType, 'connected')),
});

describe('ProviderSettingsScreen', () => {
  it('connects a disconnected provider', async () => {
    const connectProvider = vi
      .fn<ProviderSettingsAdapter['connectProvider']>()
      .mockImplementation(async (providerType) => createProvider(providerType, 'connected'));
    const adapter = buildAdapter(
      [createProvider('gmail', 'disconnected'), createProvider('outlook', 'disconnected')],
      { connectProvider },
    );

    render(<ProviderSettingsScreen adapter={adapter} />);

    const gmailCard = await screen.findByTestId('provider-card-gmail');
    await userEvent.click(within(gmailCard).getByRole('button', { name: 'Connect' }));

    await waitFor(() => {
      expect(connectProvider).toHaveBeenCalledWith('gmail');
      expect(within(gmailCard).getByText('Connected')).toBeInTheDocument();
      expect(within(gmailCard).getByRole('button', { name: 'Re-auth' })).toBeInTheDocument();
    });
  });

  it('supports re-auth then disconnect for a connected provider', async () => {
    const reauthProvider = vi
      .fn<ProviderSettingsAdapter['reauthProvider']>()
      .mockImplementation(async (providerType) => createProvider(providerType, 'connected'));
    const disconnectProvider = vi
      .fn<ProviderSettingsAdapter['disconnectProvider']>()
      .mockImplementation(async (providerType) => createProvider(providerType, 'disconnected'));
    const adapter = buildAdapter(
      [createProvider('gmail', 'connected'), createProvider('outlook', 'disconnected')],
      { disconnectProvider, reauthProvider },
    );

    render(<ProviderSettingsScreen adapter={adapter} />);

    const gmailCard = await screen.findByTestId('provider-card-gmail');
    await userEvent.click(within(gmailCard).getByRole('button', { name: 'Re-auth' }));

    await waitFor(() => {
      expect(reauthProvider).toHaveBeenCalledWith('gmail');
      expect(within(gmailCard).getByText('Connected')).toBeInTheDocument();
    });

    await userEvent.click(within(gmailCard).getByRole('button', { name: 'Disconnect' }));

    await waitFor(() => {
      expect(disconnectProvider).toHaveBeenCalledWith('gmail');
      expect(within(gmailCard).getByText('Disconnected')).toBeInTheDocument();
      expect(within(gmailCard).getByRole('button', { name: 'Connect' })).toBeInTheDocument();
    });
  });

  it('renders a recoverable action error when connect fails', async () => {
    const connectProvider = vi
      .fn<ProviderSettingsAdapter['connectProvider']>()
      .mockRejectedValue(new Error('oauth start failed'));
    const adapter = buildAdapter(
      [createProvider('gmail', 'disconnected'), createProvider('outlook', 'disconnected')],
      { connectProvider },
    );

    render(<ProviderSettingsScreen adapter={adapter} />);

    const gmailCard = await screen.findByTestId('provider-card-gmail');
    await userEvent.click(within(gmailCard).getByRole('button', { name: 'Connect' }));

    await waitFor(() => {
      expect(connectProvider).toHaveBeenCalledWith('gmail');
      expect(screen.getByRole('alert')).toHaveTextContent('oauth start failed');
      expect(within(gmailCard).getByRole('button', { name: 'Connect' })).toBeEnabled();
    });
  });
});
