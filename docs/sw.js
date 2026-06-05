// ══════════════════════════════════════════════════════
// My Stock Analyst — Service Worker
// ══════════════════════════════════════════════════════

const CACHE_NAME = 'msa-v6';
const QUEUE_STORE = 'offline-queue';
const DB_NAME = 'msa-sw-db';
const DB_VERSION = 1;

// ── IndexedDB helper ──
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        db.createObjectStore(QUEUE_STORE, { autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// ── Install ──
self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache =>
      cache.addAll(['./', './index.html', './manifest.json'])
        .catch(() => { /* offline install — ignore missing assets */ })
    )
  );
});

// ── Activate ──
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── Fetch: cache-first for same-origin, network-first for API calls ──
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Pass through non-GET requests and cross-origin API calls
  if (event.request.method !== 'GET') return;
  if (url.hostname !== self.location.hostname) return;

  // Network-first for all same-origin requests so app updates roll out immediately.
  // Falls back to cache when offline.
  if (url.hostname === self.location.hostname) {
    event.respondWith(
      fetch(event.request).then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() =>
        caches.match(event.request).then(cached =>
          cached || caches.match('./index.html') ||
          new Response('', { status: 503, statusText: 'Offline' })
        )
      )
    );
  }
});

// ── Message: receive offline queue entries from the page (B1-3) ──
self.addEventListener('message', (event) => {
  if (event.data?.type === 'QUEUE_SYNC') {
    const { op, table, payload } = event.data;
    openDB().then(db => {
      const tx = db.transaction(QUEUE_STORE, 'readwrite');
      tx.objectStore(QUEUE_STORE).add({
        op, table, payload, created_at: Date.now()
      });
    }).catch(err => console.warn('SW queue write failed:', err));
  }
});

// ── Background sync: replay queued mutations when online ──
self.addEventListener('sync', (event) => {
  if (event.tag === 'replay-queue') {
    event.waitUntil(replayQueue());
  }
});

async function replayQueue() {
  const db = await openDB();
  const tx = db.transaction(QUEUE_STORE, 'readwrite');
  const store = tx.objectStore(QUEUE_STORE);
  const entries = await new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  // Individual replay would call Supabase REST API here
  // For now: clear queue on successful sync signal (entries are replayed by the page)
  if (entries.length) {
    await new Promise((resolve, reject) => {
      const clearTx = db.transaction(QUEUE_STORE, 'readwrite');
      const clearReq = clearTx.objectStore(QUEUE_STORE).clear();
      clearReq.onsuccess = resolve;
      clearReq.onerror = reject;
    });
  }
}
