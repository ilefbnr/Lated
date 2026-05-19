// =============================================================================
// services/apiClient.ts — REST client base
// =============================================================================
//
// Thin fetch wrapper that:
//   - prefixes NEXT_PUBLIC_API_URL,
//   - attaches the analyst's bearer token (NEXT_PUBLIC_API_TOKEN by default,
//     overridable at runtime via setAuthToken — useful when a real login
//     screen is added later),
//   - parses JSON,
//   - throws a typed ApiError on non-2xx so callers can branch on `.status`
//     or `.code` without parsing strings.
// =============================================================================

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export interface ApiClient {
  get<T>(path: string, params?: Record<string, unknown>): Promise<T>;
  post<T>(path: string, body?: unknown): Promise<T>;
}

const DEFAULT_BASE_URL = 'http://localhost:8000';
const DEFAULT_DEV_TOKEN = 'analyst-token';
const TOKEN_STORAGE_KEY = 'lated.auth.token';

let overrideToken: string | null = null;

function readPersistedToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writePersistedToken(token: string | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (token === null) window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    else window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } catch {
    /* swallow */
  }
}

export function setAuthToken(token: string | null): void {
  overrideToken = token;
  writePersistedToken(token);
}

export function getAuthToken(): string | null {
  if (overrideToken !== null) return overrideToken;
  const persisted = readPersistedToken();
  if (persisted !== null && persisted.length > 0) {
    overrideToken = persisted;
    return persisted;
  }
  const envToken = process.env.NEXT_PUBLIC_API_TOKEN;
  if (typeof envToken === 'string' && envToken.length > 0) return envToken;
  return DEFAULT_DEV_TOKEN;
}

export function clearAuthToken(): void {
  overrideToken = null;
  writePersistedToken(null);
}

export function getApiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (typeof url === 'string' && url.length > 0) return url.replace(/\/$/, '');
  return DEFAULT_BASE_URL;
}

function buildUrl(path: string, params?: Record<string, unknown>): string {
  const base = getApiBaseUrl();
  const safePath = path.startsWith('/') ? path : `/${path}`;
  const url = new URL(base + safePath);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null) continue;
      if (Array.isArray(value)) {
        for (const item of value) url.searchParams.append(key, String(item));
      } else {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

function buildHeaders(extra?: Record<string, string>): HeadersInit {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(extra ?? {}),
  };
  const token = getAuthToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function parseErrorBody(response: Response): Promise<{ code: string; message: string }> {
  try {
    const data = await response.clone().json();
    if (data && typeof data === 'object') {
      const code = typeof data.code === 'string' ? data.code : `HTTP_${response.status}`;
      const message =
        typeof data.detail === 'string'
          ? data.detail
          : typeof data.message === 'string'
            ? data.message
            : response.statusText;
      return { code, message };
    }
  } catch {
    /* fallthrough */
  }
  return { code: `HTTP_${response.status}`, message: response.statusText };
}

async function request<T>(
  method: 'GET' | 'POST',
  path: string,
  options: { params?: Record<string, unknown>; body?: unknown } = {},
): Promise<T> {
  const url = buildUrl(path, options.params);
  const init: RequestInit = {
    method,
    headers: buildHeaders(method === 'POST' ? { 'Content-Type': 'application/json' } : undefined),
  };
  if (method === 'POST' && options.body !== undefined) {
    init.body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (err) {
    throw new ApiError(0, 'NETWORK_ERR', err instanceof Error ? err.message : 'network error');
  }

  if (!response.ok) {
    const { code, message } = await parseErrorBody(response);
    throw new ApiError(response.status, code, message);
  }

  if (response.status === 204) return undefined as unknown as T;
  return (await response.json()) as T;
}

export function createApiClient(): ApiClient {
  return {
    get: <T>(path: string, params?: Record<string, unknown>) =>
      request<T>('GET', path, { params }),
    post: <T>(path: string, body?: unknown) => request<T>('POST', path, { body }),
  };
}

export const apiClient: ApiClient = createApiClient();
