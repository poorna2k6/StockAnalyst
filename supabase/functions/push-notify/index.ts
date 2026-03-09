/**
 * push-notify — Supabase Edge Function (Deno)
 *
 * Sends a Web Push notification to a user.
 * Called internally by alerts-cron when a price alert triggers.
 *
 * POST /functions/v1/push-notify  (internal — should only be called by other Edge Functions)
 * Body: { userId: string, title: string, body: string, ticker: string }
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL         = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const VAPID_PUBLIC_KEY     = Deno.env.get("VAPID_PUBLIC_KEY")!;
const VAPID_PRIVATE_KEY    = Deno.env.get("VAPID_PRIVATE_KEY")!;
const VAPID_EMAIL          = Deno.env.get("VAPID_EMAIL") ?? "mailto:admin@example.com";

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: { "Access-Control-Allow-Origin": "*" } });
  }

  const { userId, title, body: msgBody, ticker } = await req.json();

  if (!userId || !title) {
    return new Response(JSON.stringify({ error: "Missing userId or title" }), { status: 400 });
  }

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

  // Fetch push subscription for this user
  const { data: prefs } = await supabase
    .from("notification_preferences")
    .select("push_enabled, push_subscription")
    .eq("user_id", userId)
    .single();

  if (!prefs?.push_enabled || !prefs?.push_subscription) {
    return new Response(JSON.stringify({ skipped: "push not enabled" }), { status: 200 });
  }

  const pushSubscription = prefs.push_subscription as {
    endpoint: string;
    keys: { p256dh: string; auth: string };
  };

  try {
    await sendWebPush(pushSubscription, {
      title,
      body: msgBody ?? "",
      ticker: ticker ?? "",
    });
    return new Response(JSON.stringify({ sent: true }), { status: 200 });
  } catch (err) {
    console.error("Push send failed:", err);
    return new Response(JSON.stringify({ error: String(err) }), { status: 500 });
  }
});

/**
 * Sends a Web Push notification using VAPID authentication.
 * Uses the Web Crypto API available in Deno.
 */
async function sendWebPush(
  subscription: { endpoint: string; keys: { p256dh: string; auth: string } },
  payload: { title: string; body: string; ticker: string },
): Promise<void> {
  const payloadBytes = new TextEncoder().encode(JSON.stringify(payload));

  // Build VAPID JWT
  const vapidJwt = await buildVapidJwt(subscription.endpoint);

  // Encrypt payload using Web Push content encryption (aes128gcm)
  const { ciphertext, serverPublicKey, salt } = await encryptPayload(
    payloadBytes,
    subscription.keys.p256dh,
    subscription.keys.auth,
  );

  const res = await fetch(subscription.endpoint, {
    method: "POST",
    headers: {
      "Authorization": `vapid t=${vapidJwt},k=${VAPID_PUBLIC_KEY}`,
      "Content-Type":  "application/octet-stream",
      "Content-Encoding": "aes128gcm",
      "TTL": "86400",
      "Crypto-Key": `dh=${uint8ToBase64url(serverPublicKey)}`,
      "Encryption":  `salt=${uint8ToBase64url(salt)}`,
    },
    body: ciphertext,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Push endpoint returned ${res.status}: ${text}`);
  }
}

/** Build a VAPID JWT for the given push endpoint origin */
async function buildVapidJwt(endpoint: string): Promise<string> {
  const origin = new URL(endpoint).origin;
  const header = base64urlEncode(JSON.stringify({ typ: "JWT", alg: "ES256" }));
  const now = Math.floor(Date.now() / 1000);
  const claims = base64urlEncode(JSON.stringify({
    aud: origin,
    exp: now + 12 * 3600,
    sub: VAPID_EMAIL,
  }));
  const sigInput = `${header}.${claims}`;

  // Import VAPID private key (base64url-encoded raw EC private key)
  const privateKeyBytes = base64urlDecode(VAPID_PRIVATE_KEY);
  const key = await crypto.subtle.importKey(
    "raw",
    privateKeyBytes,
    { name: "ECDSA", namedCurve: "P-256" },
    false,
    ["sign"],
  ).catch(async () => {
    // Try pkcs8 format if raw fails
    const pkcs8 = buildPkcs8(privateKeyBytes);
    return crypto.subtle.importKey("pkcs8", pkcs8, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  });

  const sig = await crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    key,
    new TextEncoder().encode(sigInput),
  );
  return `${sigInput}.${uint8ToBase64url(new Uint8Array(sig))}`;
}

/** Minimal aes128gcm payload encryption per RFC 8291 */
async function encryptPayload(
  plaintext: Uint8Array,
  recipientPublicKeyBase64: string,
  authBase64: string,
): Promise<{ ciphertext: Uint8Array; serverPublicKey: Uint8Array; salt: Uint8Array }> {
  const authSecret = base64urlDecode(authBase64);
  const recipientPublicKey = base64urlDecode(recipientPublicKeyBase64);
  const salt = crypto.getRandomValues(new Uint8Array(16));

  // Generate server ECDH key pair
  const serverKeyPair = await crypto.subtle.generateKey(
    { name: "ECDH", namedCurve: "P-256" },
    true,
    ["deriveBits"],
  );

  // Export server public key (uncompressed)
  const serverPublicKeyExported = await crypto.subtle.exportKey("raw", serverKeyPair.publicKey);
  const serverPublicKey = new Uint8Array(serverPublicKeyExported);

  // Import recipient's public key
  const recipientKey = await crypto.subtle.importKey(
    "raw",
    recipientPublicKey,
    { name: "ECDH", namedCurve: "P-256" },
    false,
    [],
  );

  // Derive shared ECDH secret
  const sharedSecret = await crypto.subtle.deriveBits(
    { name: "ECDH", public: recipientKey },
    serverKeyPair.privateKey,
    256,
  );

  // HKDF to derive content encryption key and nonce (simplified — full impl per RFC 8188)
  const prk = await hkdf(new Uint8Array(sharedSecret), authSecret, concat(
    new TextEncoder().encode("WebPush: info\0"),
    recipientPublicKey,
    serverPublicKey,
  ), 32);

  const contentKey = await crypto.subtle.importKey("raw", prk.slice(0, 16), "AES-GCM", false, ["encrypt"]);
  const nonce = prk.slice(16, 28);

  // Add padding (1 byte delimiter 0x02)
  const padded = new Uint8Array(plaintext.length + 2);
  padded.set(plaintext);
  padded[plaintext.length] = 0x02; // padding delimiter per aes128gcm

  const encrypted = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce, tagLength: 128 },
    contentKey,
    padded,
  );

  return {
    ciphertext: new Uint8Array(encrypted),
    serverPublicKey,
    salt,
  };
}

/** Minimal HKDF-SHA256 */
async function hkdf(ikm: Uint8Array, salt: Uint8Array, info: Uint8Array, length: number): Promise<Uint8Array> {
  const saltKey = await crypto.subtle.importKey("raw", salt, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const prk = new Uint8Array(await crypto.subtle.sign("HMAC", saltKey, ikm));
  const prkKey = await crypto.subtle.importKey("raw", prk, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const block = new Uint8Array(await crypto.subtle.sign("HMAC", prkKey, concat(info, new Uint8Array([1]))));
  return block.slice(0, length);
}

// ── Utility helpers ──────────────────────────────────────────────────────────

function concat(...arrays: Uint8Array[]): Uint8Array {
  const total = arrays.reduce((s, a) => s + a.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const a of arrays) { result.set(a, offset); offset += a.length; }
  return result;
}

function base64urlEncode(str: string): string {
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

function uint8ToBase64url(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

function base64urlDecode(str: string): Uint8Array {
  const base64 = str.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(str.length / 4) * 4, "=");
  const binary = atob(base64);
  return new Uint8Array([...binary].map((c) => c.charCodeAt(0)));
}

/** Wrap a raw 32-byte EC private key in minimal PKCS#8 DER for P-256 */
function buildPkcs8(rawKey: Uint8Array): ArrayBuffer {
  const oid = new Uint8Array([0x06, 0x07, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01]);
  const curve = new Uint8Array([0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07]);
  const inner = concat(new Uint8Array([0x02, 0x01, 0x01, 0x04, 0x20]), rawKey);
  const seq1 = concat(new Uint8Array([0x30, oid.length + curve.length + 2]), oid, new Uint8Array([0x06]), curve);
  const ecKey = concat(new Uint8Array([0x30, inner.length]), inner);
  const full = concat(new Uint8Array([0x02, 0x01, 0x00]), seq1, new Uint8Array([0x04, ecKey.length]), ecKey);
  return concat(new Uint8Array([0x30, full.length]), full).buffer;
}
