const BASE = '';

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return null;
  const contentType = res.headers.get('content-type') || '';
  return contentType.includes('application/json') ? res.json() : res.text();
}

const json = (obj) => JSON.stringify(obj);

export const api = {
  authStatus: () => request('/api/auth/status'),
  setup: (username, password) => request('/api/auth/setup', { method: 'POST', body: json({ username, password }) }),
  login: (username, password) => request('/api/auth/login', { method: 'POST', body: json({ username, password }) }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),

  listDevices: () => request('/api/devices'),
  getDevice: (id) => request(`/api/devices/${id}`),
  updateDevice: (id, body) => request(`/api/devices/${id}`, { method: 'PATCH', body: json(body) }),
  deleteDevice: (id) => request(`/api/devices/${id}`, { method: 'DELETE' }),

  setUrl: (id, url) => request(`/api/devices/${id}/url`, { method: 'POST', body: json({ url }) }),
  reboot: (id) => request(`/api/devices/${id}/reboot`, { method: 'POST' }),
  restartBrowser: (id) => request(`/api/devices/${id}/browser/restart`, { method: 'POST' }),
  rotate: (id, rotation) => request(`/api/devices/${id}/rotate`, { method: 'POST', body: json({ rotation }) }),
  screenshot: (id) => request(`/api/devices/${id}/screenshot`),
  updateAgent: (id) => request(`/api/devices/${id}/update`, { method: 'POST' }),
  networkConfig: (id, body) => request(`/api/devices/${id}/network`, { method: 'POST', body: json(body) }),
  getSettings: (id) => request(`/api/devices/${id}/settings`),
  setSettings: (id, body) => request(`/api/devices/${id}/settings`, { method: 'POST', body: json(body) }),

  getPlaylist: (id) => request(`/api/devices/${id}/playlist`),
  setPlaylist: (id, body) => request(`/api/devices/${id}/playlist`, { method: 'POST', body: json(body) }),
  clearPlaylist: (id) => request(`/api/devices/${id}/playlist`, { method: 'DELETE' }),
  activatePlaylist: (id) => request(`/api/devices/${id}/playlist/activate`, { method: 'POST' }),
  deletePlaylistImage: (id, index) => request(`/api/devices/${id}/playlist/images/${index}`, { method: 'DELETE' }),
  uploadPlaylistImage: (id, file) => {
    const form = new FormData();
    form.append('image', file);
    return request(`/api/devices/${id}/playlist/images`, { method: 'POST', body: form });
  },

  listRooms: () => request('/api/rooms'),
  createRoom: (name) => request('/api/rooms', { method: 'POST', body: json({ name }) }),
  deleteRoom: (id) => request(`/api/rooms/${id}`, { method: 'DELETE' }),

  listUrls: () => request('/api/urls'),
  createUrl: (name, url) => request('/api/urls', { method: 'POST', body: json({ name, url }) }),
  deleteUrl: (id) => request(`/api/urls/${id}`, { method: 'DELETE' }),

  pendingPairings: () => request('/api/pair/pending'),
  claimPairing: (code, name, room_id) => request('/api/pair/claim', { method: 'POST', body: json({ code, name, room_id }) }),
};

export { ApiError };
