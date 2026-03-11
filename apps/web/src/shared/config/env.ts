type RuntimeEnv = 'local' | 'development' | 'staging' | 'production';

const readEnv = (key: string): string | undefined => {
  const raw = import.meta.env[key as keyof ImportMetaEnv];
  if (typeof raw !== 'string') {
    return undefined;
  }
  const value = raw.trim();
  return value.length > 0 ? value : undefined;
};

const requireEnv = (key: string): string => {
  const value = readEnv(key);
  if (!value) {
    throw new Error(`[env] Missing required variable: ${key}`);
  }
  return value;
};

const normalizeBaseUrl = (value: string): string => {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(`[env] Invalid URL in VITE_API_BASE_URL: ${value}`);
  }

  if (parsed.search || parsed.hash) {
    throw new Error('[env] VITE_API_BASE_URL must not include query or hash');
  }

  const normalizedPath = parsed.pathname.replace(/\/+$/, '');
  return `${parsed.origin}${normalizedPath === '/' ? '' : normalizedPath}`;
};

const parseTimeout = (raw?: string): number => {
  if (!raw) {
    return 15000;
  }

  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`[env] VITE_API_TIMEOUT_MS must be a positive number, got: ${raw}`);
  }
  return parsed;
};

const parseRuntimeEnv = (raw?: string): RuntimeEnv => {
  if (!raw) {
    return import.meta.env.PROD ? 'production' : 'local';
  }
  if (raw === 'local' || raw === 'development' || raw === 'staging' || raw === 'production') {
    return raw;
  }
  throw new Error(
    `[env] VITE_APP_ENV must be one of: local, development, staging, production. Got: ${raw}`,
  );
};

export interface FrontendEnv {
  apiBaseUrl: string;
  apiKey?: string;
  controlPlaneKey?: string;
  apiTimeoutMs: number;
  appEnv: RuntimeEnv;
}

export const frontendEnv: Readonly<FrontendEnv> = Object.freeze({
  apiBaseUrl: normalizeBaseUrl(requireEnv('VITE_API_BASE_URL')),
  apiKey: readEnv('VITE_API_KEY'),
  controlPlaneKey: readEnv('VITE_CONTROL_PLANE_KEY'),
  apiTimeoutMs: parseTimeout(readEnv('VITE_API_TIMEOUT_MS')),
  appEnv: parseRuntimeEnv(readEnv('VITE_APP_ENV')),
});
