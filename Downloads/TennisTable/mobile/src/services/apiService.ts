import AsyncStorage from '@react-native-async-storage/async-storage';

const API_URL_KEY = '@tt_api_url';
const TOKEN_KEY = '@tt_access_token';
const REFRESH_KEY = '@tt_refresh_token';

export async function getApiUrl(): Promise<string> {
  return (await AsyncStorage.getItem(API_URL_KEY)) ?? 'http://localhost:8000';
}

export async function setApiUrl(url: string): Promise<void> {
  await AsyncStorage.setItem(API_URL_KEY, url.replace(/\/$/, ''));
}

async function getToken(): Promise<string | null> {
  return AsyncStorage.getItem(TOKEN_KEY);
}

async function setTokens(access: string, refresh: string): Promise<void> {
  await AsyncStorage.multiSet([[TOKEN_KEY, access], [REFRESH_KEY, refresh]]);
}

async function refreshAccessToken(): Promise<boolean> {
  try {
    const base = await getApiUrl();
    const refresh = await AsyncStorage.getItem(REFRESH_KEY);
    if (!refresh) return false;
    const res = await fetch(`${base}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    await setTokens(data.access_token, data.refresh_token ?? refresh);
    return true;
  } catch {
    return false;
  }
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const base = await getApiUrl();
  const token = await getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let res = await fetch(`${base}${path}`, { ...options, headers });

  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      const newToken = await getToken();
      if (newToken) headers['Authorization'] = `Bearer ${newToken}`;
      res = await fetch(`${base}${path}`, { ...options, headers });
    }
  }
  return res;
}

export async function login(username: string, password: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const base = await getApiUrl();
    const res = await fetch(`${base}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err.detail ?? 'Identifiants incorrects' };
    }
    const data = await res.json();
    await setTokens(data.access_token, data.refresh_token ?? '');
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: e.message ?? 'Connexion impossible' };
  }
}

export async function register(username: string, password: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err.detail ?? 'Inscription échouée' };
    }
    return login(username, password);
  } catch (e: any) {
    return { ok: false, error: e.message ?? 'Connexion impossible' };
  }
}

export async function logout(): Promise<void> {
  await AsyncStorage.multiRemove([TOKEN_KEY, REFRESH_KEY]);
}

export async function isLoggedIn(): Promise<boolean> {
  return !!(await getToken());
}

export async function testConnection(): Promise<boolean> {
  try {
    const base = await getApiUrl();
    const res = await fetch(`${base}/health`, { signal: AbortSignal.timeout(5000) });
    return res.ok;
  } catch {
    return false;
  }
}

export async function syncMatch(matchData: Record<string, unknown>): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await apiFetch('/sessions/', {
      method: 'POST',
      body: JSON.stringify(matchData),
    });
    return { ok: res.ok, error: res.ok ? undefined : 'Sync échouée' };
  } catch (e: any) {
    return { ok: false, error: e.message };
  }
}

export async function getLeaderboard(): Promise<unknown[]> {
  try {
    const res = await apiFetch('/leaderboard/');
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : (data.items ?? []);
  } catch {
    return [];
  }
}

export async function getAiRecommendations(playerId: string): Promise<string[]> {
  try {
    const res = await apiFetch(`/analysis/recommendations/${playerId}`);
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.tips) ? data.tips : [];
  } catch {
    return [];
  }
}
