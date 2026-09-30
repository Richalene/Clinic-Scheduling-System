const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
let accessToken = null;
let refreshPromise = null;
let sessionVersion = 0;

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.status = status;
  }
}

export function clearSession() {
  accessToken = null;
  sessionVersion += 1;
}

function errorMessage(data, status) {
  if (Array.isArray(data?.detail)) {
    return data.detail.map((item) => `${item.loc?.slice(1).join(' ') || 'Request'}: ${item.msg}`).join('. ');
  }
  if (typeof data?.detail === 'string') return data.detail;
  return status >= 500 ? 'The clinic server could not complete this request. Please try again.' : 'Unable to complete your request.';
}

export async function refreshSession() {
  if (!refreshPromise) {
    const version = sessionVersion;
    refreshPromise = request('/auth/refresh', { method: 'POST', authenticated: false })
      .then((data) => {
        if (version !== sessionVersion) throw new ApiError('Session ended.', 401);
        accessToken = data.access_token;
        return data;
      })
      .finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function request(path, { authenticated = true, retry = true, ...options } = {}) {
  const sentToken = accessToken;
  const headers = new Headers(options.headers);
  if (authenticated && accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  if (options.body && !(options.body instanceof URLSearchParams) && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  let response;
  try {
    response = await fetch(`${base}${path}`, { ...options, headers, credentials: 'include' });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('Unable to reach the clinic server. Please try again.');
  }
  if (response.status === 401 && authenticated) {
    if (retry && accessToken) {
      // Another in-flight request may already have refreshed this old token.
      if (sentToken !== accessToken) return request(path, { ...options, authenticated, retry: false });
      try {
        await refreshSession();
      } catch (error) {
        if (error.status !== 401 && error.status !== 403) throw error;
        clearSession();
        window.dispatchEvent(new Event('clinic:session-expired'));
        throw new ApiError('Your session has expired. Please sign in again.', 401);
      }
      return request(path, { ...options, authenticated, retry: false });
    }
    clearSession();
    window.dispatchEvent(new Event('clinic:session-expired'));
    throw new ApiError('Your session has expired. Please sign in again.', 401);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(errorMessage(data, response.status), response.status);
  return data;
}

export async function login(email, password) {
  const data = await request('/auth/login', {
    method: 'POST', authenticated: false,
    body: new URLSearchParams({ username: email, password }),
  });
  accessToken = data.access_token;
  return request('/users/me');
}

export async function logout() {
  try {
    await request('/auth/logout', { method: 'POST' });
  } finally {
    clearSession();
  }
}

export const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) });

// Catalog endpoints return plain arrays. Follow every page so selection lists
// do not silently hide patients, staff, or resources beyond the first 100.
export async function all(path, signal) {
  const rows = [];
  for (let skip = 0; ; skip += 100) {
    const page = await request(`${path}${path.includes('?') ? '&' : '?'}skip=${skip}&limit=100`, { signal });
    rows.push(...page);
    if (page.length < 100) return rows;
  }
}
