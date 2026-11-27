import type { ImportError } from './types';

export class ApiError extends Error {
  constructor(
    public code: string,
    public detail: string | ImportError[],
    public status: number,
  ) {
    super(typeof detail === 'string' ? detail : code);
  }
}

function csrfToken(): string {
  const cookie = document.cookie.split('; ').find((part) => part.startsWith('csrftoken='));
  return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
}

/** Calls the API. Writes carry CSRF and a fresh idempotency key, reused on a single network retry. */
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const write = body !== undefined;
  const options: RequestInit = {
    credentials: 'same-origin',
    method: write ? 'POST' : 'GET',
    headers: write
      ? { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken(), 'Idempotency-Key': crypto.randomUUID() }
      : {},
    ...(write ? { body: JSON.stringify(body) } : {}),
  };
  let response: Response;
  try {
    response = await fetch('/api/v1' + path, options);
  } catch {
    response = await fetch('/api/v1' + path, options);
  }
  if (!response.headers.get('content-type')?.includes('application/json')) {
    throw new ApiError('UNEXPECTED_RESPONSE', '', response.status);
  }
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === 'string' || Array.isArray(data.detail) ? data.detail : '';
    throw new ApiError(data.code || 'REQUEST_FAILED', detail, response.status);
  }
  return data as T;
}
