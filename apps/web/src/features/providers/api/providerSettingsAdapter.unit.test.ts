import { describe, expect, it, vi } from 'vitest';
import { AUTH_ACCESS_TOKEN_STORAGE_KEY } from '../../../app/authSession.constants';
import {
  createLocalProviderSettingsAdapter,
  createProviderSettingsApiAdapter,
} from './providerSettingsAdapter';

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

describe('createProviderSettingsApiAdapter', () => {
  it('lists providers through the live API and maps response fields', async () => {
    window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, 'provider-token');
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              connection_status: 'connected',
              display_name: 'Ops Gmail',
              id: 'prov-gmail',
              last_error_message: null,
              provider_type: 'gmail',
              updated_at: '2026-03-17T10:00:00.000Z',
            },
          ],
        }),
        {
          headers: {
            'content-type': 'application/json',
          },
          status: 200,
        },
      ),
    );
    const adapter = createProviderSettingsApiAdapter({
      apiBaseUrl: 'http://127.0.0.1:18000',
      fetchImpl,
    });

    const providers = await adapter.listProviders();

    expect(fetchImpl).toHaveBeenCalledWith(
      'http://127.0.0.1:18000/v1/providers?limit=10&offset=0',
      expect.objectContaining({
        credentials: 'include',
        headers: expect.objectContaining({
          Authorization: 'Bearer provider-token',
        }),
        method: 'GET',
      }),
    );
    expect(providers).toEqual([
      {
        connectionStatus: 'connected',
        displayName: 'Ops Gmail',
        id: 'prov-gmail',
        lastErrorMessage: null,
        providerType: 'gmail',
        updatedAt: '2026-03-17T10:00:00.000Z',
      },
    ]);
  });

  it('posts provider test-connection and maps success/failure payload fields', async () => {
    window.localStorage.setItem(AUTH_ACCESS_TOKEN_STORAGE_KEY, 'provider-token');
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith('/v1/providers?limit=10&offset=0')) {
        return new Response(
          JSON.stringify({
            items: [
              {
                connection_status: 'connected',
                display_name: 'Ops Gmail',
                id: 'prov-gmail',
                last_error_message: null,
                provider_type: 'gmail',
                updated_at: '2026-03-17T10:00:00.000Z',
              },
            ],
          }),
          {
            headers: {
              'content-type': 'application/json',
            },
            status: 200,
          },
        );
      }

      return new Response(
        JSON.stringify({
          message: 'provider is not connected',
          provider: {
            connection_status: 'disconnected',
            display_name: 'Ops Gmail',
            id: 'prov-gmail',
            last_error_message: 'provider is not connected',
            provider_type: 'gmail',
            updated_at: '2026-03-17T10:01:00.000Z',
          },
          request_id: 'req-provider-test-failed',
          status: 'failure',
          tested_at: '2026-03-17T10:01:00.000Z',
        }),
        {
          headers: {
            'content-type': 'application/json',
          },
          status: 200,
        },
      );
    });
    const adapter = createProviderSettingsApiAdapter({
      apiBaseUrl: 'http://127.0.0.1:18000',
      fetchImpl,
    });

    const result = await adapter.testProviderConnection('gmail');

    expect(fetchImpl).toHaveBeenCalledWith(
      'http://127.0.0.1:18000/v1/providers/prov-gmail/test-connection',
      expect.objectContaining({
        credentials: 'include',
        headers: expect.objectContaining({
          Authorization: 'Bearer provider-token',
        }),
        method: 'POST',
      }),
    );
    expect(result).toEqual({
      message: 'provider is not connected',
      provider: {
        connectionStatus: 'disconnected',
        displayName: 'Ops Gmail',
        id: 'prov-gmail',
        lastErrorMessage: 'provider is not connected',
        providerType: 'gmail',
        updatedAt: '2026-03-17T10:01:00.000Z',
      },
      requestId: 'req-provider-test-failed',
      status: 'failure',
      testedAt: '2026-03-17T10:01:00.000Z',
    });
  });
});
