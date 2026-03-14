import { getApiRequestId, normalizeApiError, type ApiError } from '../../../shared/api/client';
import { frontendEnv } from '../../../shared/config/env';

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  status: string;
}

export interface AuthTenant {
  id: string;
  slug: string;
  name: string;
}

export interface AuthSessionMetadata {
  session_id: string;
  access_expires_at: string;
  refresh_expires_at: string;
}

interface AuthErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id?: string;
    details?: Record<string, unknown>;
  };
}

interface AuthSuccessBase {
  user: AuthUser;
  tenant: AuthTenant;
  session: AuthSessionMetadata;
}

export interface LoginRequest {
  email: string;
  password: string;
  tenant_slug: string;
}

export interface LoginResponse extends AuthSuccessBase {
  access_token: string;
  expires_in: number;
  token_type: 'Bearer';
}

export interface RefreshResponse {
  access_token: string;
  expires_in: number;
  token_type: 'Bearer';
  session: AuthSessionMetadata;
}

export type MeResponse = AuthSuccessBase;

export interface AuthApiError extends ApiError {
  code?: string;
  details?: Record<string, unknown>;
}

export type AuthApiResult<T> =
  | {
      ok: true;
      data: T;
    }
  | {
      ok: false;
      error: AuthApiError;
    };

const readBody = async (response: Response): Promise<unknown | undefined> => {
  if (response.status === 204) {
    return undefined;
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (!(contentType.includes('application/json') || contentType.includes('+json'))) {
    return undefined;
  }

  try {
    return await response.json();
  } catch {
    return undefined;
  }
};

const isAuthErrorEnvelope = (value: unknown): value is AuthErrorEnvelope => {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const errorValue = (value as Record<string, unknown>).error;
  if (!errorValue || typeof errorValue !== 'object') {
    return false;
  }

  const record = errorValue as Record<string, unknown>;
  return typeof record.code === 'string' && typeof record.message === 'string';
};

const toAuthApiError = async (
  response: Response,
  body: unknown | undefined,
): Promise<AuthApiError> => {
  if (isAuthErrorEnvelope(body)) {
    return {
      code: body.error.code,
      details: body.error.details,
      message: body.error.message,
      requestId: body.error.request_id ?? getApiRequestId(response),
      status: response.status,
    };
  }

  const normalized = await normalizeApiError(new Error('Auth request failed'), response);
  return {
    ...normalized,
    status: response.status,
  };
};

const toAuthApiNetworkError = async (error: unknown): Promise<AuthApiError> => {
  const normalized = await normalizeApiError(error);
  return {
    ...normalized,
  };
};

const authRequest = async <T>(
  path: string,
  init: RequestInit,
): Promise<AuthApiResult<T>> => {
  let response: Response;

  try {
    response = await fetch(`${frontendEnv.apiBaseUrl}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        ...(init.headers ?? {}),
      },
    });
  } catch (error) {
    return {
      ok: false,
      error: await toAuthApiNetworkError(error),
    };
  }

  const body = await readBody(response);

  if (!response.ok) {
    return {
      ok: false,
      error: await toAuthApiError(response, body),
    };
  }

  return {
    ok: true,
    data: body as T,
  };
};

export const loginWithPassword = (payload: LoginRequest): Promise<AuthApiResult<LoginResponse>> =>
  authRequest<LoginResponse>('/auth/login', {
    body: JSON.stringify(payload),
    headers: {
      'Content-Type': 'application/json',
    },
    method: 'POST',
  });

export const refreshAccessToken = (): Promise<AuthApiResult<RefreshResponse>> =>
  authRequest<RefreshResponse>('/auth/refresh', {
    method: 'POST',
  });

export const logoutSession = (): Promise<AuthApiResult<undefined>> =>
  authRequest<undefined>('/auth/logout', {
    method: 'POST',
  });

export const fetchMe = (accessToken: string): Promise<AuthApiResult<MeResponse>> =>
  authRequest<MeResponse>('/v1/me', {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    method: 'GET',
  });
