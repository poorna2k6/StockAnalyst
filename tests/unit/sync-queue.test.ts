/**
 * Unit tests for the service worker's IndexedDB sync queue logic
 * Tests the core queue semantics in isolation using fake-indexeddb
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import 'fake-indexeddb/auto';

// Inline queue implementation (mirrors sw.js logic) for testability
const DB_NAME = 'msa_sw_db';
const QUEUE_STORE = 'msa_sync_queue';
const DB_VERSION = 1;

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e: IDBVersionChangeEvent) => {
      const db = (e.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        db.createObjectStore(QUEUE_STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = (e: Event) => resolve((e.target as IDBOpenDBRequest).result);
    req.onerror = () => reject(req.error);
  });
}

async function enqueue(db: IDBDatabase, record: object): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readwrite');
    tx.objectStore(QUEUE_STORE).add(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getAllQueued(db: IDBDatabase): Promise<object[]> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readonly');
    const req = tx.objectStore(QUEUE_STORE).getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function deleteFromQueue(db: IDBDatabase, id: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readwrite');
    tx.objectStore(QUEUE_STORE).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

describe('SW sync queue — enqueue', () => {
  let db: IDBDatabase;

  beforeEach(async () => {
    // Fresh IndexedDB per test (fake-indexeddb resets on new open with fresh name)
    db = await openDB();
    // Clear queue
    const all = await getAllQueued(db);
    for (const r of all as Array<{ id: number }>) {
      await deleteFromQueue(db, r.id);
    }
  });

  it('enqueues an upsert operation', async () => {
    await enqueue(db, {
      op: 'upsert',
      table: 'positions',
      payload: { portfolio_id: 'p1', ticker: 'AAPL', shares: 10, avg_cost: 150 },
      created_at: Date.now(),
    });
    const queued = await getAllQueued(db);
    expect(queued).toHaveLength(1);
    expect((queued[0] as { op: string }).op).toBe('upsert');
    expect((queued[0] as { table: string }).table).toBe('positions');
  });

  it('enqueues a delete operation', async () => {
    await enqueue(db, {
      op: 'delete',
      table: 'positions',
      payload: { match: { portfolio_id: 'p1', ticker: 'AAPL' } },
      created_at: Date.now(),
    });
    const queued = await getAllQueued(db);
    expect(queued).toHaveLength(1);
    expect((queued[0] as { op: string }).op).toBe('delete');
  });

  it('queues multiple operations in order', async () => {
    await enqueue(db, { op: 'upsert', table: 'positions', payload: { ticker: 'AAPL' }, created_at: 1 });
    await enqueue(db, { op: 'upsert', table: 'positions', payload: { ticker: 'MSFT' }, created_at: 2 });
    await enqueue(db, { op: 'delete', table: 'watchlist_items', payload: { ticker: 'TSLA' }, created_at: 3 });
    const queued = (await getAllQueued(db)) as Array<{ op: string; payload: { ticker: string } }>;
    expect(queued).toHaveLength(3);
    expect(queued[0].payload.ticker).toBe('AAPL');
    expect(queued[1].payload.ticker).toBe('MSFT');
    expect(queued[2].payload.ticker).toBe('TSLA');
  });
});

describe('SW sync queue — replay', () => {
  let db: IDBDatabase;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    db = await openDB();
    // Clear queue
    const all = await getAllQueued(db);
    for (const r of all as Array<{ id: number }>) {
      await deleteFromQueue(db, r.id);
    }

    // Mock fetch for replay
    fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    globalThis.fetch = fetchMock;
  });

  it('replays an upsert by POSTing to Supabase REST', async () => {
    const record = {
      op: 'upsert',
      table: 'positions',
      payload: { portfolio_id: 'p1', ticker: 'AAPL', shares: 10, avg_cost: 150 },
      supabaseUrl: 'https://test.supabase.co',
      anonKey: 'anon-key',
      accessToken: 'jwt-token',
      created_at: Date.now(),
    };
    await enqueue(db, record);

    // Simulate replay
    const queued = (await getAllQueued(db)) as Array<{
      id: number;
      op: string;
      table: string;
      payload: object;
      supabaseUrl: string;
      anonKey: string;
      accessToken: string;
    }>;
    for (const r of queued) {
      await fetch(`${r.supabaseUrl}/rest/v1/${r.table}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          apikey: r.anonKey,
          Authorization: `Bearer ${r.accessToken}`,
          Prefer: 'resolution=merge-duplicates,return=minimal',
        },
        body: JSON.stringify(r.payload),
      });
      await deleteFromQueue(db, r.id);
    }

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://test.supabase.co/rest/v1/positions');
    expect(opts.method).toBe('POST');

    // Record should be removed after successful replay
    const remaining = await getAllQueued(db);
    expect(remaining).toHaveLength(0);
  });

  it('leaves failed records in queue on HTTP error', async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 503 });
    const record = {
      op: 'upsert',
      table: 'positions',
      payload: { ticker: 'AAPL' },
      supabaseUrl: 'https://test.supabase.co',
      anonKey: 'anon-key',
      accessToken: 'jwt-token',
      created_at: Date.now(),
    };
    await enqueue(db, record);

    const queued = (await getAllQueued(db)) as Array<{
      id: number;
      op: string;
      table: string;
      supabaseUrl: string;
      anonKey: string;
      accessToken: string;
      payload: object;
    }>;
    for (const r of queued) {
      try {
        const res = await fetch(`${r.supabaseUrl}/rest/v1/${r.table}`, {
          method: 'POST',
          headers: {},
          body: JSON.stringify(r.payload),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        await deleteFromQueue(db, r.id);
      } catch {
        // Leave in queue
      }
    }

    const remaining = await getAllQueued(db);
    expect(remaining).toHaveLength(1); // Still in queue
  });
});
