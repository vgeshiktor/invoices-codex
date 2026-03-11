import type { Auth } from './generated/core/auth.gen';
import { client as generatedClient } from './generated/client.gen';
import { frontendEnv } from '../config/env';

export interface ApiError {
  message: string;
  status?: number;
  requestId?: string;
  cause?: unknown;
}

const getRequestId = (response?: Response): string | undefined =>
  response?.headers.get('x-request-id') ?? response?.headers.get('X-Request-Id') ?? undefined;

const toErrorMessage = (error: unknown): string => {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  if (typeof error === 'string' && error.trim().length > 0) {
    return error;
  }
  if (error && typeof error === 'object') {
    const fromRecord = error as Record<string, unknown>;
    if (typeof fromRecord.detail === 'string' && fromRecord.detail.trim().length > 0) {
      return fromRecord.detail;
    }
    if (typeof fromRecord.message === 'string' && fromRecord.message.trim().length > 0) {
      return fromRecord.message;
    }
  }
  return 'Unexpected API error';
};

const timeoutFetch: typeof fetch = async (input, init) => {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), frontendEnv.apiTimeoutMs);
  const sourceSignal = init?.signal;

  if (sourceSignal) {
    if (sourceSignal.aborted) {
      controller.abort(sourceSignal.reason);
    } else {
      sourceSignal.addEventListener('abort', () => controller.abort(sourceSignal.reason), {
        once: true,
      });
    }
  }

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
};

const resolveAuthToken = (auth: Auth): string | undefined => {
  if (auth.name === 'X-API-Key') {
    return frontendEnv.apiKey;
  }
  if (auth.name === 'X-Control-Plane-Key') {
    return frontendEnv.controlPlaneKey;
  }
  return undefined;
};

generatedClient.setConfig({
  auth: resolveAuthToken,
  baseUrl: frontendEnv.apiBaseUrl,
  fetch: timeoutFetch,
});

export const apiClient = generatedClient;

export const normalizeApiError = (error: unknown, response?: Response): ApiError => ({
  cause: error,
  message: toErrorMessage(error),
  requestId: getRequestId(response),
  status: response?.status,
});

export const getApiRequestId = getRequestId;
