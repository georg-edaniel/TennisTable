import AsyncStorage from '@react-native-async-storage/async-storage';

const API_URL_KEY = '@tt_api_url';
const TOKEN_KEY = '@tt_access_token';
const REFRESH_KEY = '@tt_refresh_token';

export async function getApiUrl(): Promise<string> {
  return (await AsyncStorage.getItem(API_URL_KEY)) ?? 'https://tennistable.onrender.com';
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
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${refresh}` },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    await setTokens(data.access_token, refresh);
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

export async function login(
  username: string,
  password: string,
): Promise<{ ok: boolean; error?: string; totpRequired?: boolean; pendingToken?: string }> {
  try {
    const base = await getApiUrl();
    const res = await fetch(`${base}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err.detail ?? 'Identifiants incorrects' };
    }
    const data = await res.json();
    if (data.totp_required) {
      return { ok: false, totpRequired: true, pendingToken: data.pending_token };
    }
    await setTokens(data.access_token, data.refresh_token ?? '');
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: e.message ?? 'Connexion impossible' };
  }
}

export async function loginTotp(
  pendingToken: string,
  code: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const base = await getApiUrl();
    const res = await fetch(`${base}/auth/totp/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pending_token: pendingToken, code }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { ok: false, error: err.detail ?? 'Code invalide' };
    }
    const data = await res.json();
    await setTokens(data.access_token, data.refresh_token ?? '');
    return { ok: true };
  } catch (e: any) {
    return { ok: false, error: e.message ?? 'Connexion impossible' };
  }
}

export async function register(
  username: string,
  password: string,
  email: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const base = await getApiUrl();
    const res = await fetch(`${base}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, email }),
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

const SYNC_QUEUE_KEY = '@tt_sync_queue';

export async function getSyncQueue(): Promise<Record<string, unknown>[]> {
  try {
    const raw = await AsyncStorage.getItem(SYNC_QUEUE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

async function addToSyncQueue(matchData: Record<string, unknown>): Promise<void> {
  const queue = await getSyncQueue();
  queue.push(matchData);
  await AsyncStorage.setItem(SYNC_QUEUE_KEY, JSON.stringify(queue));
}

async function removeFromSyncQueue(index: number): Promise<void> {
  const queue = await getSyncQueue();
  queue.splice(index, 1);
  await AsyncStorage.setItem(SYNC_QUEUE_KEY, JSON.stringify(queue));
}

async function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export async function syncMatch(matchData: Record<string, unknown>): Promise<{ ok: boolean; error?: string }> {
  const MAX_RETRIES = 3;
  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const res = await apiFetch('/api/sessions/manual-match', {
        method: 'POST',
        body: JSON.stringify(matchData),
      });
      if (res.ok) return { ok: true };
      if (res.status >= 400 && res.status < 500) {
        // Client error — don't retry, queue for manual review
        break;
      }
    } catch {
      // Network error — retry with backoff
    }
    if (attempt < MAX_RETRIES - 1) await sleep(1000 * (attempt + 1));
  }
  // Queue for later retry
  await addToSyncQueue(matchData);
  return { ok: false, error: 'Sync échouée — ajouté à la file d\'attente' };
}

/** Retry all queued matches. Returns { success, failed } counts. */
export async function flushSyncQueue(): Promise<{ success: number; failed: number }> {
  const queue = await getSyncQueue();
  if (queue.length === 0) return { success: 0, failed: 0 };

  let success = 0;
  let failed = 0;
  const remaining: Record<string, unknown>[] = [];

  for (const item of queue) {
    try {
      const res = await apiFetch('/api/sessions/manual-match', {
        method: 'POST',
        body: JSON.stringify(item),
      });
      if (res.ok) {
        success++;
      } else {
        failed++;
        remaining.push(item);
      }
    } catch {
      failed++;
      remaining.push(item);
    }
  }

  await AsyncStorage.setItem(SYNC_QUEUE_KEY, JSON.stringify(remaining));
  return { success, failed };
}

export async function getLeaderboard(): Promise<unknown[]> {
  try {
    const res = await apiFetch('/api/leaderboard');
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : (data.items ?? []);
  } catch {
    return [];
  }
}

export async function getAiRecommendations(playerId: string): Promise<string[]> {
  try {
    const res = await apiFetch(`/api/analysis/training-vs-match/${playerId}`);
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.tips) ? data.tips : [];
  } catch {
    return [];
  }
}
