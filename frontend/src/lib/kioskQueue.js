// Cola local CIFRADA del quiosco de visitantes (sin dependencias): si falla el
// internet, el registro se guarda cifrado con AES-GCM (clave no exportable,
// generada en la tableta y guardada como CryptoKey en IndexedDB) y se reenvía
// con la MISMA clave de idempotencia al volver la conexión.
const DB_NAME = 'vv-kiosk';
const STORE = 'queue';
const KEYS = 'keys';

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => { request.result.createObjectStore(STORE, { keyPath: 'id' }); request.result.createObjectStore(KEYS); };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function tx(db, store, mode, run) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(store, mode);
    const result = run(transaction.objectStore(store));
    transaction.oncomplete = () => resolve(result?.result ?? result);
    transaction.onerror = () => reject(transaction.error);
  });
}

async function cryptoKey(db) {
  const existing = await new Promise((resolve) => { const request = db.transaction(KEYS).objectStore(KEYS).get('main'); request.onsuccess = () => resolve(request.result); request.onerror = () => resolve(null); });
  if (existing) return existing;
  const key = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
  await tx(db, KEYS, 'readwrite', (store) => store.put(key, 'main'));
  return key;
}

export async function enqueue(payload) {
  const db = await openDb();
  const key = await cryptoKey(db);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const data = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, new TextEncoder().encode(JSON.stringify(payload)));
  await tx(db, STORE, 'readwrite', (store) => store.put({ id: payload.idempotency_key, iv, data, queued_at: Date.now() }));
}

export async function pendingCount() {
  try {
    const db = await openDb();
    return await new Promise((resolve) => { const request = db.transaction(STORE).objectStore(STORE).count(); request.onsuccess = () => resolve(request.result); request.onerror = () => resolve(0); });
  } catch { return 0; }
}

/** Envía lo pendiente; `send(payload)` debe lanzar error si no hubo respuesta del servidor. */
export async function flush(send) {
  let db;
  try { db = await openDb(); } catch { return 0; }
  const key = await cryptoKey(db);
  const items = await new Promise((resolve) => { const request = db.transaction(STORE).objectStore(STORE).getAll(); request.onsuccess = () => resolve(request.result || []); request.onerror = () => resolve([]); });
  let sent = 0;
  for (const item of items) {
    try {
      const payload = JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: item.iv }, key, item.data)));
      await send(payload);
      await tx(db, STORE, 'readwrite', (store) => store.delete(item.id));
      sent += 1;
    } catch (error) {
      if (error?.permanent) await tx(db, STORE, 'readwrite', (store) => store.delete(item.id));
      else break; // sigue sin internet: se intenta más tarde
    }
  }
  return sent;
}
