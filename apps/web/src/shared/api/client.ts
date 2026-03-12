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

const isAbortError = (error: unknown): error is Error =>
  error instanceof Error && error.name === 'AbortError';

const isTimeoutError = (error: unknown): error is Error =>
  error instanceof Error && error.name === 'TimeoutError';

const extractMessageFromValue = (value: unknown): string | undefined => {
  if (typeof value === 'string' && value.trim().length > 0) {
    return value;
  }

  if (!value || typeof value !== 'object') {
    return undefined;
  }

  const record = value as Record<string, unknown>;

  if (typeof record.detail === 'string' && record.detail.trim().length > 0) {
    return record.detail;
  }

  if (typeof record.message === 'string' && record.message.trim().length > 0) {
    return record.message;
  }

  if (Array.isArray(record.detail)) {
    const first = record.detail[0];
    if (typeof first === 'string' && first.trim().length > 0) {
      return first;
    }

    if (first && typeof first === 'object') {
      const firstRecord = first as Record<string, unknown>;
      if (typeof firstRecord.msg === 'string' && firstRecord.msg.trim().length > 0) {
        return firstRecord.msg;
      }
    }
  }

  return undefined;
};

const readResponseErrorBody = async (response?: Response): Promise<unknown | undefined> => {
  if (!response || response.bodyUsed) {
    return undefined;
  }

  try {
    const clonedResponse = response.clone();
    const contentType = clonedResponse.headers.get('content-type') ?? '';
    if (contentType.includes('application/json') || contentType.includes('+json')) {
      return await clonedResponse.json();
    }

    const text = await clonedResponse.text();
    return text.trim().length > 0 ? text : undefined;
  } catch {
    return undefined;
  }
};

const toErrorMessage = (error: unknown, responseBody?: unknown, response?: Response): string => {
  if (isTimeoutError(error)) {
    return error.message;
  }

  if (isAbortError(error)) {
    return 'Request was canceled before completion';
  }

  const messageFromErrorValue = extractMessageFromValue(error);
  if (messageFromErrorValue) {
    return messageFromErrorValue;
  }

  const messageFromResponseBody = extractMessageFromValue(responseBody);
  if (messageFromResponseBody) {
    return messageFromResponseBody;
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }

  if (response?.status) {
    return `Request failed with HTTP ${response.status}`;
  }

  return 'Unexpected API error';
};

const timeoutFetch: typeof fetch = async (input, init) => {
  const controller = new AbortController();
  let didTimeout = false;
  const timeoutId = globalThis.setTimeout(() => {
    didTimeout = true;
    controller.abort(new DOMException('Request timed out', 'TimeoutError'));
  }, frontendEnv.apiTimeoutMs);
  const requestSignal = input instanceof Request ? input.signal : undefined;
  const sourceSignals = [init?.signal, requestSignal].filter(
    (signal): signal is AbortSignal => signal !== undefined,
  );
  const cleanupCallbacks: Array<() => void> = [];

  for (const signal of sourceSignals) {
    if (signal.aborted) {
      if (!controller.signal.aborted) {
        controller.abort(signal.reason);
      }
      continue;
    }

    const onAbort = () => {
      if (!controller.signal.aborted) {
        controller.abort(signal.reason);
      }
    };
    signal.addEventListener('abort', onAbort, { once: true });
    cleanupCallbacks.push(() => signal.removeEventListener('abort', onAbort));
  }

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (didTimeout && isAbortError(error)) {
      const timeoutError = new Error(
        `Request timed out after ${frontendEnv.apiTimeoutMs}ms`,
      );
      timeoutError.name = 'TimeoutError';
      throw timeoutError;
    }
    throw error;
  } finally {
    for (const cleanup of cleanupCallbacks) {
      cleanup();
    }
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

  throw new Error(
    `[api] Unsupported auth header name "${String(auth.name)}". Update resolveAuthToken for new security schemes.`,
  );
};

generatedClient.setConfig({
  auth: resolveAuthToken,
  baseUrl: frontendEnv.apiBaseUrl,
  fetch: timeoutFetch,
});

export const apiClient = generatedClient;

export const normalizeApiError = async (error: unknown, response?: Response): Promise<ApiError> => {
  const responseBody = await readResponseErrorBody(response);

  return {
    cause: error,
    message: toErrorMessage(error, responseBody, response),
    requestId: getRequestId(response),
    status: response?.status,
  };
};

export const getApiRequestId = getRequestId;
