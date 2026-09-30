import { beforeEach, describe, expect, it, vi } from 'vitest';

let api;
const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
beforeEach(async () => {
  vi.resetModules();
  api = await import('../api');
});

describe('API authentication and contracts', () => {
  it('sends form-encoded login and keeps the token out of browser storage', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response({ access_token: 'access-one' })).mockResolvedValueOnce(response({ user_id: 3 }));
    vi.stubGlobal('fetch', fetch);
    expect(await api.login('mary@example.com', 'test-password')).toEqual({ user_id: 3 });
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/api/auth/login');
    expect(options.body).toBeInstanceOf(URLSearchParams);
    expect(options.body.get('username')).toBe('mary@example.com');
    expect(fetch.mock.calls[1][1].headers.get('Authorization')).toBe('Bearer access-one');
    expect(options.credentials).toBe('include');
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it('refreshes an expired access token once and retries the original request', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(response({ access_token: 'old' }))
      .mockResolvedValueOnce(response({ user_id: 3 }))
      .mockResolvedValueOnce(response({ detail: 'Expired' }, 401))
      .mockResolvedValueOnce(response({ access_token: 'new' }))
      .mockResolvedValueOnce(response([{ appointment_id: 7 }]));
    vi.stubGlobal('fetch', fetch);
    await api.login('mary@example.com', 'password');
    expect(await api.request('/appointments/')).toEqual([{ appointment_id: 7 }]);
    expect(fetch.mock.calls[3][0]).toBe('/api/auth/refresh');
    expect(fetch.mock.calls[4][1].headers.get('Authorization')).toBe('Bearer new');
  });

  it('shares simultaneous refresh requests', async () => {
    const fetch = vi.fn().mockResolvedValue(response({ access_token: 'new' }));
    vi.stubGlobal('fetch', fetch);
    await Promise.all([api.refreshSession(), api.refreshSession(), api.refreshSession()]);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('does not retry login failures or turn database conflicts into success', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response({ detail: 'Invalid email or password' }, 401))
      .mockResolvedValueOnce(response({ detail: 'Slot is no longer available' }, 409));
    vi.stubGlobal('fetch', fetch);
    await expect(api.login('mary@example.com', 'wrong')).rejects.toMatchObject({ status: 401, message: 'Invalid email or password' });
    expect(fetch).toHaveBeenCalledTimes(1);
    await expect(api.post('/appointments/', {})).rejects.toMatchObject({ status: 409 });
  });

  it('reads all catalog pages and formats validation errors', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response(Array.from({ length: 100 }, (_, i) => ({ patient_id: i + 1 }))))
      .mockResolvedValueOnce(response([{ patient_id: 101 }]))
      .mockResolvedValueOnce(response({ detail: [{ loc: ['body', 'start_at'], msg: 'Timezone required' }] }, 422));
    vi.stubGlobal('fetch', fetch);
    expect(await api.all('/patients/')).toHaveLength(101);
    expect(fetch.mock.calls[1][0]).toBe('/api/patients/?skip=100&limit=100');
    await expect(api.post('/appointments/', {})).rejects.toThrow('start_at: Timezone required');
  });
});
