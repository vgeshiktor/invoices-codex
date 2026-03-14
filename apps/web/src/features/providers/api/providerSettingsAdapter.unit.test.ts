import { describe, expect, it } from 'vitest';
import { createLocalProviderSettingsAdapter } from './providerSettingsAdapter';

describe('createLocalProviderSettingsAdapter', () => {
  it('does not allow callers to mutate internal provider state through listProviders response', async () => {
    const adapter = createLocalProviderSettingsAdapter();

    const initialProviders = await adapter.listProviders();
    initialProviders[0].displayName = 'Tampered';
    initialProviders.push({
      connectionStatus: 'connected',
      displayName: 'Injected',
      id: 'injected',
      lastErrorMessage: null,
      providerType: 'gmail',
      updatedAt: '2026-03-14T00:00:00.000Z',
    });

    const nextProviders = await adapter.listProviders();

    expect(nextProviders).toHaveLength(2);
    expect(nextProviders.find((provider) => provider.providerType === 'gmail')?.displayName).toBe(
      'Gmail',
    );
  });
});
