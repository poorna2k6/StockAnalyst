/**
 * StockAnalyst Service Worker
 * - Cache-first strategy for static assets
 * - IndexedDB sync queue for offline data mutations
 * - Background Sync API to flush queue on reconnect
 * - Web Push notification handler for price alerts
 */

const CACHE_NAME = 'msa-v1';
const SYNC_TAG = 'msa-data-sync';
const DB_NAME = 'msa_sw_db';
const QUEUE_STORE = 'msa_sync_queue';
const DB_VERSION = 1;

// Assets to cache on install
const PRECACHE_URLS = [
  './',
  './index.html',
  './manifest.json',
];

// ─── Install ──────────────────────────────────────────────────────────────────

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

// ─── Activate ─────────────────────────────────────────────────────────────────

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ─── Fetch — cache-first for navigation, network-first for API calls ──────────

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Don't intercept Supabase API calls or external APIs
  if (
    url.hostname.includes('supabase.co') ||
    url.hostname.includes('anthropic.com') ||
    url.hostname.includes('googleapis.com') ||
    url.hostname.includes('finance.yahoo.com') ||
    url.hostname.includes('cdn.jsdelivr.net')
  ) {
    return; // Let browser handle these normally
  }

  // Cache-first for same-origin requests (the PWA shell)
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => {
          // Offline fallback: return cached index.html for navigation requests
          if (event.request.mode === 'navigate') {
            return caches.match('./index.html');
          }
          return new Response('Offline', { status: 503 });
        });
      })
    );
  }
});

// ─── Background Sync — flush IndexedDB sync queue ─────────────────────────────

self.addEventListener('sync', (event) => {
  if (event.tag === SYNC_TAG) {
    event.waitUntil(flushSyncQueue());
  }
});

async function flushSyncQueue() {
  const db = await openDB();
  const tx = db.transaction(QUEUE_STORE, 'readonly');
  const store = tx.objectStore(QUEUE_STORE);
  const all = await getAllRecords(store);
  await tx.done;

  for (const record of all) {
    try {
      await replayOperation(record);
      // Remove successfully replayed item
      const delTx = db.transaction(QUEUE_STORE, 'readwrite');
      delTx.objectStore(QUEUE_STORE).delete(record.id);
      await delTx.done;
    } catch (err) {
      // Leave failed items in queue for next sync attempt
      console.warn('[SW] Sync replay failed for record', record.id, err);
    }
  }
}

async function replayOperation(record) {
  const { op, table, payload, supabaseUrl, anonKey, accessToken } = record;

  if (!supabaseUrl || !accessToken) {
    throw new Error('Missing supabase credentials in sync record');
  }

  const headers = {
    'Content-Type': 'application/json',
    'apikey': anonKey,
    'Authorization': `Bearer ${accessToken}`,
    'Prefer': op === 'upsert' ? 'resolution=merge-duplicates' : '',
  };

  const baseUrl = `${supabaseUrl}/rest/v1/${table}`;

  if (op === 'upsert') {
    const res = await fetch(baseUrl, {
      method: 'POST',
      headers: { ...headers, 'Prefer': 'resolution=merge-duplicates,return=minimal' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } else if (op === 'delete') {
    const { match } = payload;
    const params = new URLSearchParams(match).toString();
    const res = await fetch(`${baseUrl}?${params}`, {
      method: 'DELETE',
      headers,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  }
}

// ─── Push Notifications — price alert triggers ────────────────────────────────

self.addEventListener('push', (event) => {
  if (!event.data) return;

  let data;
  try {
    data = event.data.json();
  } catch {
    data = { title: 'StockAnalyst Alert', body: event.data.text() };
  }

  const { title = 'Price Alert', body = '', ticker = '', url = './' } = data;

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: './icons/icon-192.png',
      badge: './icons/icon-72.png',
      tag: `alert-${ticker}`,
      renotify: true,
      data: { url },
      actions: [
        { action: 'view', title: 'View Chart' },
        { action: 'dismiss', title: 'Dismiss' },
      ],
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if (event.action === 'dismiss') return;

  const url = event.notification.data?.url || './';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      const existing = clients.find((c) => c.url.includes('StockAnalyst'));
      if (existing) {
        existing.focus();
        existing.postMessage({ type: 'ALERT_CLICKED', url });
      } else {
        self.clients.openWindow(url);
      }
    })
  );
});

// ─── IndexedDB helpers ────────────────────────────────────────────────────────

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        const store = db.createObjectStore(QUEUE_STORE, { keyPath: 'id', autoIncrement: true });
        store.createIndex('created_at', 'created_at');
      }
    };
    req.onsuccess = (e) => resolve(wrapDB(e.target.result));
    req.onerror = () => reject(req.error);
  });
}

// Minimal promise wrapper around IDBDatabase
function wrapDB(db) {
  return {
    transaction(store, mode) {
      const tx = db.transaction(store, mode);
      return {
        objectStore: (name) => wrapStore(tx.objectStore(name)),
        done: new Promise((res, rej) => {
          tx.oncomplete = res;
          tx.onerror = () => rej(tx.error);
          tx.onabort = () => rej(tx.error);
        }),
      };
    },
  };
}

function wrapStore(store) {
  return {
    getAll: () => new Promise((res, rej) => {
      const req = store.getAll();
      req.onsuccess = () => res(req.result);
      req.onerror = () => rej(req.error);
    }),
    delete: (key) => new Promise((res, rej) => {
      const req = store.delete(key);
      req.onsuccess = () => res();
      req.onerror = () => rej(req.error);
    }),
    add: (val) => new Promise((res, rej) => {
      const req = store.add(val);
      req.onsuccess = () => res(req.result);
      req.onerror = () => rej(req.error);
    }),
  };
}

async function getAllRecords(store) {
  return store.getAll();
}
