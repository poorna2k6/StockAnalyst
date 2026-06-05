# My Stock Analyst — User Profile Management Integration Analysis

**Date:** 2026-03-08
**App Version:** v2.3
**Document Type:** Product + Systems Analysis

---

## Executive Summary

My Stock Analyst is a mature single-HTML PWA with a well-structured localStorage data model (`msa_portfolio`, `msa_watchlist`, `msa_alerts`, `msa_key`, `msa_gemini`, `msa_ai_pref`, `msa_dark`, `msa_name`). Introducing user profiles unlocks multi-device sync, advisor-client relationships, and SaaS billing — but it fundamentally changes the app's trust model. The current architecture stores sensitive API keys in plaintext localStorage; a profile system must fix this as a first-order concern.

**Top recommendation:** Supabase (PostgreSQL + Auth + Storage) with Google/Apple OAuth as the primary sign-in method, phased over 12 weeks. This gives the best cost-to-capability ratio for a solo developer targeting both retail consumers and financial advisors.

---

## 1. User Profile Use Cases

### 1.1 What Data Should Live in a Profile vs. Remain Local

**Cloud Profile (synced across devices)**

| Data | Reason |
|---|---|
| Portfolio positions (`msa_portfolio`) | Core asset — users expect this on every device |
| Watchlist (`msa_watchlist`) | High churn; users add tickers on mobile, review on desktop |
| Price alerts (`msa_alerts`) | Alerts need to fire from a server, not just a browser tab |
| User name / display name | Identity |
| AI provider preference (`msa_ai_pref`) | Preference should follow the user |
| Subscription tier / feature flags | Cannot live client-side (trivially spoofable) |
| AI query credit balance | Must be server-authoritative |
| Notification preferences | Server-side push notifications require server-stored subscriptions |
| Advisor-client relationships | Relational data; cannot exist locally |

**Device-Local Only (do NOT sync)**

| Data | Reason |
|---|---|
| `msa_key` (Anthropic key) | Third-party secret; should move to encrypted server storage, not synced localStorage |
| `msa_gemini` (Google key) | Same as above |
| `msa_dark` (dark mode toggle) | Device-level UI preference; jarring if it changes mid-session from another device |
| Active tab state | Session-only UI state |
| Cached stock quotes (`quotes` object) | Ephemeral market data; always refetch |
| Chat history (`chatHistory`) | Conversational context is session-scoped; optionally sync last N messages |

**Special Case — API Keys:**
The current app stores API keys as plaintext in localStorage, accessible to any JavaScript on the page. On migration to a profile system, user-owned API keys should be stored server-side as AES-256-GCM encrypted values (encrypted with a key derived from the user's auth token, stored in Supabase Vault or AWS Secrets Manager). The frontend receives a short-lived session token, not the raw API key. The backend proxies AI calls, injecting the decrypted key server-side. This is the single highest-impact security improvement the profile migration delivers.

### 1.2 Multi-Device Sync Scenarios

**Scenario A — Phone + Desktop (Same User)**
A user adds NVDA to their portfolio on mobile at lunch. When they open the app on desktop that evening, the position should be present.

Implementation: optimistic local write + background sync. On add/edit/delete, write to localStorage immediately for instant UI feedback, then POST to API. On app load, fetch latest from server and merge. Conflict resolution: last-write-wins by `updated_at` timestamp on each record.

**Scenario B — Offline Add Then Reconnect**
User is on a plane, adds 3 positions. On reconnect, all 3 sync to the server.

Implementation: IndexedDB-based sync queue. Each mutation is stored as an operation `{op, entity, payload, created_at, synced: false}`. A service worker background sync event flushes the queue when connectivity returns.

**Scenario C — Simultaneous Edits (Phone + Desktop Open)**
User edits the same position from two tabs/devices at once.

Implementation: Supabase Realtime subscriptions. The desktop tab subscribes to `portfolios:user_id=eq.{uid}`. When the server receives the mobile update, the desktop tab receives a Postgres NOTIFY event and re-renders. Last write wins; no merge required for portfolio positions (they are full-object replacements, not partial field patches).

### 1.3 Multiple Portfolios Per User

The current schema stores one flat portfolio object. A profile system should model portfolios as first-class entities.

Use cases: "My Roth IRA", "My Taxable Brokerage", "Kids' College Fund", "Trading Account."

Each portfolio is a separate entity with its own positions, name, type tag, and currency. The Portfolio tab gains a dropdown/switcher. AI analysis is always scoped to the active portfolio, but the Overview tab can show aggregate across all portfolios.

### 1.4 Family/Spouse Shared Portfolios

Model: A portfolio has an `owner_user_id` and an optional array of `collaborators: [{user_id, role: 'viewer'|'editor'}]`.

Sharing flow: Owner sends invite link (email or deep link). Recipient accepts. Both see the portfolio in their portfolio list, labeled "Shared." Editors can add/remove positions. Viewers can only read.

Important: A shared portfolio is **not** a copy. There is one authoritative record, and all collaborators read/write the same Supabase row. Realtime sync keeps all viewers current.

### 1.5 Advisor-Client Relationships

This is covered in depth in Section 6. At a high level:

- Advisor accounts have an `account_type: 'advisor'` flag and a `firm_name`.
- Advisors create client records and link them to specific portfolios they manage.
- Clients can optionally have their own login (with restricted view) or exist as read-only records managed entirely by the advisor.
- The advisor sees all client portfolios in an "Advisor Dashboard" tab that replaces the standard Portfolio tab when `account_type === 'advisor'`.

---

## 2. Profile Schema Design

### 2.1 Core User Profile

```sql
-- users table (mirrors Supabase auth.users, extended)
CREATE TABLE profiles (
  id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email           TEXT UNIQUE NOT NULL,
  display_name    TEXT,
  avatar_url      TEXT,
  account_type    TEXT NOT NULL DEFAULT 'retail'    -- 'retail' | 'advisor'
                  CHECK (account_type IN ('retail', 'advisor')),
  firm_name       TEXT,                              -- advisor only
  subscription_tier TEXT NOT NULL DEFAULT 'free'
                  CHECK (subscription_tier IN ('free', 'pro', 'advisor')),
  subscription_status TEXT DEFAULT 'active'
                  CHECK (subscription_status IN ('active', 'past_due', 'canceled', 'trialing')),
  trial_ends_at   TIMESTAMPTZ,
  stripe_customer_id TEXT,
  ai_provider     TEXT DEFAULT 'auto'
                  CHECK (ai_provider IN ('auto', 'claude', 'gemini')),
  -- API keys: encrypted at rest via Supabase Vault / pgcrypto
  -- Do NOT store as plaintext columns
  ai_credits_remaining INTEGER DEFAULT 50,         -- for managed-key mode
  ai_credits_reset_at  TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 2.2 Portfolios

```sql
CREATE TABLE portfolios (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id        UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  name            TEXT NOT NULL DEFAULT 'My Portfolio',
  portfolio_type  TEXT DEFAULT 'personal'
                  CHECK (portfolio_type IN ('personal', 'shared', 'advisor_managed', 'demo')),
  currency        TEXT DEFAULT 'USD',
  cash_balance    NUMERIC(18,2) DEFAULT 0,
  is_default      BOOLEAN DEFAULT FALSE,
  sort_order      INTEGER DEFAULT 0,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Portfolio positions
CREATE TABLE positions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id    UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  ticker          TEXT NOT NULL,
  shares          NUMERIC(18,6) NOT NULL CHECK (shares > 0),
  avg_cost        NUMERIC(18,4) NOT NULL CHECK (avg_cost > 0),
  notes           TEXT,
  added_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(portfolio_id, ticker)
);
```

### 2.3 Watchlist and Alerts

```sql
CREATE TABLE watchlist_items (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  ticker          TEXT NOT NULL,
  sort_order      INTEGER DEFAULT 0,
  added_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, ticker)
);

CREATE TABLE price_alerts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  ticker          TEXT NOT NULL,
  condition       TEXT NOT NULL CHECK (condition IN ('above', 'below')),
  target_price    NUMERIC(18,4) NOT NULL,
  is_active       BOOLEAN DEFAULT TRUE,
  triggered_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 2.4 Portfolio Collaborators (Sharing)

```sql
CREATE TABLE portfolio_collaborators (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id    UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  user_id         UUID REFERENCES profiles(id) ON DELETE CASCADE,
  invited_email   TEXT,                              -- before user accepts
  role            TEXT NOT NULL DEFAULT 'viewer'
                  CHECK (role IN ('viewer', 'editor')),
  invite_token    TEXT UNIQUE,
  accepted_at     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 2.5 Settings: Profile-Level vs. Device-Level

**Profile-Level (stored in Supabase)**
- `ai_provider` preference
- `display_name`
- Notification preferences (email digest, price alert delivery channel)
- Subscription tier
- Risk tolerance default (used to pre-populate Investment Planner)
- Default currency
- AI credit balance

**Device-Level (stored in localStorage, never synced)**
- `msa_dark` — dark mode toggle
- Active tab on last close
- Cached quote data (with TTL)
- Draft chat input
- Encrypted session token (short-lived JWT from Supabase Auth)

### 2.6 Notification Preferences

```sql
CREATE TABLE notification_preferences (
  user_id             UUID PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
  price_alerts_email  BOOLEAN DEFAULT TRUE,
  price_alerts_push   BOOLEAN DEFAULT TRUE,
  weekly_digest_email BOOLEAN DEFAULT FALSE,
  ai_credit_warning   BOOLEAN DEFAULT TRUE,          -- when < 10 credits
  portfolio_summary   TEXT DEFAULT 'weekly'
                      CHECK (portfolio_summary IN ('never', 'daily', 'weekly')),
  updated_at          TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3. Authentication Options

### 3.1 Comparison Matrix

| Criterion | Magic Link | Google/Apple OAuth | Username/Password | API-Key-Only (current) |
|---|---|---|---|---|
| Implementation effort (solo dev) | Low | Low–Medium | Medium–High | None |
| UX quality (consumer) | Good (requires email) | Excellent (1 tap) | Poor (friction, forgot password) | Poor (no identity) |
| UX quality (advisor B2B) | Acceptable | Good | Acceptable | Not viable |
| Security | High (no passwords to breach) | High (delegates to Google/Apple) | Medium (bcrypt required, breach risk) | None |
| Offline capability | Works after initial auth | Works after initial auth | Works after initial auth | Always works |
| B2B / enterprise SSO path | No | Limited (Google Workspace) | SAML possible | No |
| Implementation time (weeks) | 0.5 | 1 | 2–3 | 0 |

### 3.2 Recommendations (Ranked)

**Recommendation: Google/Apple OAuth as primary + Magic Link as fallback**

**Rank 1 — Google OAuth + Apple Sign-In**
- Users are already on Gmail or have Apple IDs. One tap, no new password.
- PWA on iOS benefits from "Sign in with Apple" native sheet.
- Supabase Auth supports both out of the box with ~20 lines of configuration.
- For B2B: advisors almost universally use Google Workspace, making Google OAuth sufficient for initial B2B rollout.
- Implementation: add `supabase.auth.signInWithOAuth({provider: 'google'})` and `supabase.auth.signInWithOAuth({provider: 'apple'})`. The callback URL updates the in-memory session and stores the Supabase JWT in localStorage.

**Rank 2 — Magic Link Email**
- Zero password UX, higher security than username/password.
- Critical as fallback for users without Google/Apple accounts.
- Works identically with Supabase: `supabase.auth.signInWithOtp({email})`.
- Slight friction: user must leave the PWA to check email on mobile (one of the few rough edges of magic links in installed PWAs).

**Rank 3 — Username/Password**
- Only add if B2B enterprise customers with strict SSO/LDAP requirements emerge.
- Introduces password reset flow, breach notification obligations, bcrypt cost.
- Not recommended for Phase 1 or Phase 2.

**Rank 4 — API-Key-Only (current)**
- Not auth. Remains as an offline/demo mode for users who explicitly decline to create an account.
- "Continue without account" option should be preserved so the app doesn't alienate privacy-conscious users.

### 3.3 Session Management in PWA Context

PWAs have no native browser session concept. Use this pattern:

1. Supabase Auth returns a JWT (access token, 1-hour expiry) and a refresh token (14-day expiry).
2. Store both in localStorage under `msa_session` (Supabase SDK does this automatically).
3. On app load, call `supabase.auth.getSession()` — this silently refreshes the access token if expired.
4. PWA install does not create a new session; the same localStorage persists in the standalone window context.
5. For sensitive operations (change email, delete account), require re-authentication via `supabase.auth.reauthenticate()`.

---

## 4. Backend Architecture Options

### 4.1 Comparison Matrix

| Criterion | Supabase | Firebase | Clerk + PlanetScale | Auth0 + Self-hosted PG |
|---|---|---|---|---|
| Free tier generosity | 500MB DB, 2GB bandwidth, 50K MAU | 1GB Firestore, 50K reads/day | 10K MAU (Clerk), free PlanetScale limited | Auth0 free: 7,500 MAU; PG: self-hosted cost |
| Monthly cost at 1,000 users | ~$0 (free tier) | ~$0–$25 | ~$25 (Clerk Pro) | ~$23+ (Auth0) + hosting |
| Monthly cost at 10,000 users | ~$25 (Pro) | ~$50–$100 | ~$100+ | ~$240+ |
| Query model | SQL (PostgreSQL) | NoSQL (document) | SQL (MySQL) | SQL (PostgreSQL) |
| Complexity for solo dev | Low | Low–Medium | Medium (two vendors) | High (ops burden) |
| Real-time support | Excellent (Postgres NOTIFY) | Excellent (native) | Polling only | Requires custom |
| Auth features | Email, OAuth, MFA | Email, OAuth | Best-in-class | Enterprise-grade |
| Row-level security | Native PostgreSQL RLS | Manual Firestore rules | Manual | Manual |
| Advisor B2B fit | Excellent (RLS handles multi-tenant) | Acceptable | Acceptable | Excellent (full control) |
| Scalability | High (Postgres scales well) | Very high | High | Highest (full control) |
| Vendor lock-in | Medium (Postgres is portable) | High (Firestore queries are proprietary) | High (two proprietary APIs) | Low (open source) |
| Local dev experience | Excellent (Supabase CLI + local Docker) | Good (Firebase emulator) | Good | Complex |

### 4.2 Recommendation: Supabase

**Supabase is the clear winner for this app context.** Reasons specific to My Stock Analyst:

1. **Relational data fits SQL perfectly.** Portfolio positions, watchlists, alerts, advisor-client relationships — these are all relational. Supabase's PostgreSQL is the right tool. Firestore's document model would require awkward denormalization.

2. **Row-Level Security eliminates a class of bugs.** With Supabase RLS, `SELECT * FROM positions WHERE portfolio_id = $1` automatically fails if the requesting user doesn't own or have access to that portfolio. This is enforced at the database layer, not the application layer — critical for a financial app.

3. **Supabase Vault for API key storage.** Supabase includes a built-in secrets manager (Vault) that encrypts values with pgsodium. User API keys (Anthropic, Google) can be stored here and decrypted only server-side.

4. **Supabase Realtime for multi-device sync.** The existing `fetchQuote` and `streamAI` functions make real-time data a familiar pattern. Extending this to portfolio sync with Supabase Realtime channels requires minimal additional JavaScript.

5. **Free tier is sufficient for launch.** 500MB database, 50,000 MAU, and 2GB bandwidth covers hundreds of active users for $0/month during early growth.

6. **Supabase Edge Functions for price alert processing.** Alerts currently require the browser to be open. A Supabase Edge Function running on a cron schedule can check prices server-side and send push notifications.

### 4.3 Supabase Architecture Diagram

```
Browser (PWA)
  │
  ├── supabase.auth.*          → Supabase Auth (JWT)
  ├── supabase.from('...')     → Supabase Data API (RLS-enforced PostgreSQL)
  ├── supabase.channel(...)    → Supabase Realtime (multi-device sync)
  └── fetch('/api/ai-proxy')   → Supabase Edge Function (AI key proxy)
                                    └── Supabase Vault (encrypted API keys)
                                    └── Anthropic / Google AI APIs
```

---

## 5. Data Migration Strategy

### 5.1 First-Login Migration Flow

When a user signs in for the first time (or links an existing anonymous session to a new account), the app detects existing localStorage data and migrates it.

**Detection logic:**
```javascript
async function migrateLocalDataIfNeeded(supabaseUser) {
  const localPortfolio = safeJsonParse('msa_portfolio', {});
  const localWatchlist = safeJsonParse('msa_watchlist', []);
  const localAlerts    = safeJsonParse('msa_alerts', {});
  const hasLocalData   = Object.keys(localPortfolio).length > 0
                         || localWatchlist.length > 0
                         || Object.keys(localAlerts).length > 0;

  if (!hasLocalData) return; // nothing to migrate

  // Check if user already has cloud data
  const { data: existingPortfolios } = await supabase
    .from('portfolios')
    .select('id')
    .eq('owner_id', supabaseUser.id)
    .limit(1);

  const hasCloudData = existingPortfolios && existingPortfolios.length > 0;

  if (hasCloudData) {
    // Conflict scenario — show resolution UI
    showMigrationConflictModal(localPortfolio, localWatchlist, localAlerts);
  } else {
    // Clean import
    await importLocalToCloud(supabaseUser.id, localPortfolio, localWatchlist, localAlerts);
    clearMigratedLocalKeys();
    toast('Your portfolio has been saved to your account.');
  }
}
```

### 5.2 Conflict Resolution

When a user signs in and both local data and cloud data exist (e.g., they used the app on a different device before, created an account, then installed on a new phone):

**Present a simple modal with three options:**

1. **Keep cloud data** — discard local, load cloud. Recommended if cloud data is more recent.
2. **Keep local data** — replace cloud with local. Recommended if local is more recent.
3. **Merge** — combine positions (cloud takes precedence for shared tickers, local adds new tickers), merge watchlists (union), merge alerts (union).

Show a diff summary: "Cloud: 4 positions, 6 watchlist items. Local: 3 positions (2 overlap), 8 watchlist items."

**Never silently discard data.** The user must explicitly confirm.

### 5.3 Offline-First Sync Strategy

The app must remain fully functional without internet. The strategy is a local-first architecture with background sync.

**Layer 1 — Local State (always authoritative for UI)**
All portfolio operations write to a local `msa_portfolio` localStorage key immediately. The UI reflects local state. This is unchanged from today.

**Layer 2 — Sync Queue (IndexedDB)**
Every mutation is appended to a sync queue stored in IndexedDB:
```javascript
const syncQueue = [
  { op: 'upsert', table: 'positions', payload: {...}, queued_at: 1234567890 },
  { op: 'delete', table: 'positions', payload: { ticker: 'AAPL', portfolio_id: '...' }, queued_at: 1234567891 },
];
```

**Layer 3 — Background Sync (Service Worker)**
The existing manifest.json already enables PWA installation. Add a service worker that:
- Registers a Background Sync event (`self.registration.sync.register('portfolio-sync')`).
- On `sync` event, flushes the queue to Supabase.
- On success, marks items as `synced: true` and removes them.
- On failure (network error), retries on next sync event.

**Layer 4 — Inbound Sync (Realtime)**
On app open with connectivity, Supabase Realtime subscription pulls any changes made on other devices since the last sync. Merge with local: server wins for any ticker already in local state (avoids phantom duplicates); local adds for tickers not in server state (from the sync queue not yet flushed).

**Conflict resolution rule:** Last `updated_at` timestamp wins. Every local mutation sets `updated_at = Date.now()`. The sync flush sends this timestamp. Supabase RLS policy: `updated_at > server.updated_at` to accept the write.

---

## 6. Advisor-Client Profile Model

### 6.1 How Advisor Accounts Differ

| Feature | Retail User | Advisor |
|---|---|---|
| `account_type` | `'retail'` | `'advisor'` |
| Portfolio tab | Personal portfolios | Client portfolio list + personal |
| Subscription | Free / Pro ($9.99) | Advisor ($49.99/month base) |
| Client seats | N/A | Up to 10 (base), unlimited (enterprise) |
| AI analysis | Own API key or credit pool | Firm-level credit pool |
| Branding | Standard | White-label firm name/logo on reports |
| Data export | CSV | CSV + PDF report per client |
| Analytics | Personal P&L | Aggregate AUM dashboard |

### 6.2 Advisor-Client Data Model

```sql
-- Advisor-client relationship
CREATE TABLE advisor_clients (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  advisor_id      UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  client_user_id  UUID REFERENCES profiles(id),          -- null until client accepts
  client_email    TEXT NOT NULL,
  client_name     TEXT NOT NULL,
  invite_token    TEXT UNIQUE,
  invite_sent_at  TIMESTAMPTZ,
  accepted_at     TIMESTAMPTZ,
  status          TEXT DEFAULT 'invited'
                  CHECK (status IN ('invited', 'active', 'suspended')),
  risk_profile    TEXT DEFAULT 'moderate'
                  CHECK (risk_profile IN ('conservative', 'moderate', 'aggressive')),
  notes           TEXT,                                   -- advisor's private notes
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Link client portfolios to advisor management
CREATE TABLE advisor_managed_portfolios (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  advisor_client_id UUID NOT NULL REFERENCES advisor_clients(id) ON DELETE CASCADE,
  portfolio_id    UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  advisor_can_edit BOOLEAN DEFAULT FALSE,                -- advisory-only vs. discretionary
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 6.3 Client Seat Management

**Invitation flow:**

1. Advisor goes to "Clients" tab → "Add Client" → enters client's email and name.
2. System creates `advisor_clients` row with `status='invited'` and generates a unique `invite_token`.
3. System sends email (via Supabase Edge Function + Resend/SendGrid): "Your advisor [name] has invited you to view your portfolio on My Stock Analyst."
4. Client clicks link → directed to sign-up/sign-in → on completion, `advisor_clients.client_user_id` is populated, `status='active'`.
5. Client sees their portfolio in a simplified read-only view. They cannot see other clients' data.
6. Advisor sees all their clients' portfolios in the Advisor Dashboard.

**Seat limits by tier:**

| Advisor Tier | Price | Client Seats |
|---|---|---|
| Advisor Starter | $49.99/month | 10 clients |
| Advisor Pro | $99.99/month | 50 clients |
| Advisor Enterprise | Custom | Unlimited + white-label |

Seat count is enforced server-side: `COUNT(*) FROM advisor_clients WHERE advisor_id = $1 AND status != 'suspended'`.

### 6.4 Permission Model

**What advisor can see:**
- Client's portfolio positions, value, P&L, allocation.
- Client's watchlist.
- Client's price alerts (read-only).
- AI analysis of client's portfolio (using firm's credit pool).

**What advisor cannot see:**
- Client's personal API keys (stored in Vault, not exposed to advisor queries).
- Client's chat history in the Analyst tab (considered personal).
- Client's device preferences (dark mode, etc.).

**What client can see:**
- Own portfolio, watchlist, alerts — exactly as a retail user.
- A banner: "Your portfolio is monitored by [Advisor Name] at [Firm]."
- An option to revoke advisor access.

**Row-Level Security enforcement:**
```sql
-- Advisor can read portfolios they manage
CREATE POLICY "advisor_read_managed_portfolios"
ON portfolios FOR SELECT
USING (
  id IN (
    SELECT amp.portfolio_id
    FROM advisor_managed_portfolios amp
    JOIN advisor_clients ac ON amp.advisor_client_id = ac.id
    WHERE ac.advisor_id = auth.uid()
    AND ac.status = 'active'
  )
);
```

### 6.5 Billing Relationship

Advisors pay for client seats directly. Clients never see a billing UI within the advisor-assigned view. Options:

- **Advisor pays for all clients** (recommended for B2B): One Stripe subscription per advisor account, billed per seat tier. Clients get a "courtesy access" account.
- **Advisor + Client split** (complex, not recommended initially): Advisor pays for platform access; clients with their own Pro subscriptions can have richer personal features. Avoid until explicitly requested.

Billing implementation: Stripe Billing with a metered usage component. Create a `stripe_customer_id` per advisor, a subscription with a `quantity` param equal to active client count. A Supabase webhook (`advisor_clients` insert/delete) triggers a Stripe subscription quantity update.

---

## 7. Privacy & Compliance

### 7.1 Data Encryption at Rest

| Data | Required Encryption | Implementation |
|---|---|---|
| Portfolio positions | Recommended | Supabase Transparent Data Encryption (TDE) on the PG cluster; optionally application-level encryption for high-value clients |
| API keys (Anthropic, Google) | Required | Supabase Vault (`vault.secrets` table using pgsodium). Keys are encrypted with a server-managed master key. Never stored as plaintext columns. |
| Price alert thresholds | Low sensitivity | TDE sufficient |
| User email | Regulated (GDPR) | TDE + avoid logging in application logs |
| Advisor notes on clients | High sensitivity | Application-level AES-256-GCM encryption before INSERT |
| AI chat history (if persisted) | High sensitivity | Application-level encryption OR do not persist at all |

**Practical guidance:** Do not store AI chat history on the server unless users explicitly opt in to "Save my chat history." Conversational data about investment decisions is sensitive and creates retention/disclosure obligations.

### 7.2 GDPR / CCPA Requirements

**User rights that must be supported:**

| Right | Implementation |
|---|---|
| Right to access | "Export my data" button in Profile Settings. Returns JSON with all portfolios, watchlist, alerts, preferences. Generate client-side from Supabase SELECT. |
| Right to deletion | "Delete my account" button. Trigger `DELETE FROM profiles WHERE id = auth.uid()` — cascades to all related tables. Also delete Stripe customer, revoke auth session, purge Vault secrets. Complete within 30 days (GDPR) or 45 days (CCPA). |
| Right to portability | Data export in JSON or CSV. Portfolios should export in a format importable by competing tools (CSV: ticker, shares, avg_cost, added_date). |
| Right to rectification | User can edit all their own data. |
| Consent for marketing | Email digest opt-in is unchecked by default. Log consent timestamp for audit trail. |
| Cookie notice | The app uses localStorage (not third-party cookies), but add a privacy notice on first load if targeting EU users. |

**Data Retention Policy:**
- Active user data: retained while account is active.
- Deleted account data: purged within 30 days (soft-delete for 7 days for accidental deletion recovery, then hard-delete).
- Audit logs (who accessed what): retained 1 year, stored in an append-only table with no user-facing delete.
- AI query logs (if any): 90-day retention maximum.

### 7.3 SEC/FINRA Implications

**Important disclaimer:** My Stock Analyst is a technology tool, not a registered investment adviser. The following applies to the distinction between tool and advice:

**Safe harbor as a technology tool:**
- The app provides data, analysis, and educational content.
- Users make their own investment decisions.
- The prominent disclaimer in the Settings modal ("Educational tool only. Not financial advice.") should also appear at the top of any AI-generated analysis output.

**Risks with advisor use case:**
- If a registered investment adviser (RIA) uses this tool to manage client portfolios, the adviser is the regulated entity. The adviser is responsible for ensuring the tool's outputs meet their fiduciary duty.
- The app itself does not execute trades, hold assets, or have custody of funds — this keeps it outside direct SEC registration requirements.
- However, if the app stores records of investment recommendations made to clients, those records may be subject to the Investment Advisers Act of 1940, Rule 204-2 (books and records). Advisors using the platform may need to retain AI-generated recommendations. Offer a PDF/email export of AI analyses for advisor accounts.

**Do not store:**
- Social Security numbers or tax IDs.
- Bank account numbers.
- Actual trade execution records (brokers' confirmations).
- Anything that would make this look like a broker-dealer platform.

### 7.4 Data Residency

For the advisor B2B market, some enterprise clients will require data to remain in a specific geography (EU, US). Supabase supports region selection per project (US East, EU West, etc.). For initial launch, US East is fine. Add EU region as a separate Supabase project when GDPR-compliant advisor clients emerge, with a flag in the sign-up flow to select region.

---

## 8. Monetization Integration

### 8.1 Tier Structure

| Tier | Price | Target | Limits |
|---|---|---|---|
| Free | $0 | Casual retail users | 1 portfolio, 5 watchlist items, 10 AI queries/month, own API key required for unlimited |
| Pro | $9.99/month | Active retail investors | 5 portfolios, unlimited watchlist, 100 AI queries/month (managed key), price alerts with push notifications |
| Advisor | $49.99/month (10 seats) | Financial advisors | Unlimited portfolios per client, 500 AI queries/month per advisor account, white-label, PDF export, client management dashboard |

**Free tier with own API key:** Users who bring their own Anthropic or Google key bypass the managed credit system entirely. This is a competitive advantage and acquisition hook — technically sophisticated users love it. It also eliminates the need to subsidize AI costs for power users.

### 8.2 AI Credit System

Credits apply only to users using the app's managed AI keys (not their own keys).

```sql
CREATE TABLE ai_query_log (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES profiles(id),
  query_type      TEXT NOT NULL         -- 'chat', 'brief', 'invest_plan', 'portfolio_analysis', 'earn_ideas'
                  CHECK (query_type IN ('chat', 'brief', 'invest_plan', 'portfolio_analysis', 'earn_ideas', 'screenshot_import')),
  tokens_in       INTEGER,
  tokens_out      INTEGER,
  model           TEXT,                 -- 'claude-sonnet-4-6' | 'gemini-2.5-flash'
  credits_used    NUMERIC(6,2) DEFAULT 1,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

**Credit costs (suggested):**
- Brief AI summary: 0.5 credits (auto-generated, background)
- Chat message: 1 credit
- Investment plan: 2 credits
- Portfolio analysis: 2 credits
- Screenshot import (vision API): 3 credits

**Monthly reset:** A Supabase cron job (pg_cron) resets `ai_credits_remaining` on the 1st of each month for active subscribers.

### 8.3 Feature Flags Per Tier

Store feature flags as a computed function in Supabase, driven by `subscription_tier`:

```sql
CREATE OR REPLACE FUNCTION get_user_limits(p_user_id UUID)
RETURNS JSONB AS $$
  SELECT CASE profiles.subscription_tier
    WHEN 'free' THEN jsonb_build_object(
      'max_portfolios', 1,
      'max_watchlist', 5,
      'ai_credits_monthly', 10,
      'price_alerts', FALSE,
      'csv_export', FALSE,
      'multi_device_sync', FALSE
    )
    WHEN 'pro' THEN jsonb_build_object(
      'max_portfolios', 5,
      'max_watchlist', 100,
      'ai_credits_monthly', 100,
      'price_alerts', TRUE,
      'csv_export', TRUE,
      'multi_device_sync', TRUE
    )
    WHEN 'advisor' THEN jsonb_build_object(
      'max_portfolios', 999,
      'max_watchlist', 999,
      'ai_credits_monthly', 500,
      'price_alerts', TRUE,
      'csv_export', TRUE,
      'multi_device_sync', TRUE,
      'client_seats', 10,
      'pdf_export', TRUE
    )
  END
  FROM profiles WHERE id = p_user_id;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;
```

**Client-side enforcement:** Do not rely on client-side feature flag checks for security. Feature limits must be enforced server-side (Edge Functions or RLS policies). Client-side flags are for UX only (showing/hiding upgrade prompts).

### 8.4 Trial Period Mechanics

- New accounts start on a 14-day Pro trial.
- `subscription_tier = 'pro'`, `subscription_status = 'trialing'`, `trial_ends_at = NOW() + INTERVAL '14 days'`.
- On day 12, send email: "Your trial ends in 2 days."
- On trial expiry: a Supabase cron job checks `trial_ends_at < NOW() AND subscription_status = 'trialing'` → sets `subscription_tier = 'free'`, `subscription_status = 'active'`.
- Users who add a payment method before expiry are immediately moved to paid Pro.
- No credit card required to start trial — reduces activation friction.

### 8.5 Stripe Integration Points

```javascript
// Edge Function: create-checkout-session
const session = await stripe.checkout.sessions.create({
  customer: profile.stripe_customer_id,
  mode: 'subscription',
  line_items: [{ price: STRIPE_PRICE_IDS[tier], quantity: 1 }],
  success_url: 'https://mystockanalyst.app/?upgrade=success',
  cancel_url:  'https://mystockanalyst.app/?upgrade=canceled',
  metadata: { user_id: userId, tier },
});
```

Webhook events to handle: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed` → update `profiles.subscription_status`.

---

## 9. Implementation Roadmap

### Phase 1 — MVP Auth (Weeks 1–4)

**Goal:** Users can sign in, their data is saved to the cloud, and multi-device sync works for the most important data (portfolio + watchlist).

**Week 1: Supabase Setup + Auth UI**
- Create Supabase project. Configure Google OAuth and magic link.
- Add Supabase JS SDK to `index.html` via CDN (`<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js">`).
- Create `profiles` table with RLS.
- Add a sign-in screen (bottom sheet modal, consistent with existing Settings modal style) with "Sign in with Google," "Sign in with Apple," and "Continue with Email."
- Add a "Sign Out" option to the Settings modal.
- **Effort:** 3 days

**Week 2: Data Migration + Cloud Write**
- Create `portfolios`, `positions`, `watchlist_items`, `price_alerts` tables with RLS policies.
- Replace direct `localStorage.setItem('msa_portfolio', ...)` calls with a data layer module (`data.js` or inline functions) that writes to both localStorage (immediate) and Supabase (async).
- Implement first-login migration: detect local data, prompt user, import to cloud.
- **Effort:** 4 days

**Week 3: Multi-Device Read + Realtime**
- On app load (authenticated), fetch portfolio and watchlist from Supabase and merge with local.
- Subscribe to Supabase Realtime channel for portfolio changes.
- Add sync indicator in the header (a subtle dot: green = synced, yellow = syncing, red = offline).
- **Effort:** 3 days

**Week 4: API Key Security + Testing**
- Move API keys from localStorage to Supabase Vault via an Edge Function.
- Update `streamAI()` function to call `/api/ai-proxy` Edge Function instead of calling Anthropic/Google directly from the browser. The Edge Function decrypts and injects the key server-side.
- Test all 6 tabs with and without connectivity.
- **Effort:** 4 days

**Phase 1 Deliverable:** Single-user cloud sync. No multi-portfolio, no advisor features.
**Phase 1 Effort Total:** ~14 developer-days (solo dev)

---

### Phase 2 — Advisor Features (Weeks 5–12)

**Goal:** Financial advisors can manage client portfolios. Billing system is live.

**Weeks 5–6: Multi-Portfolio**
- Add `portfolios` switcher UI to the Portfolio tab header.
- "Add Portfolio" flow (name, type).
- All data queries scoped to `active_portfolio_id` (stored in localStorage, not synced — each device remembers its own active portfolio).
- **Effort:** 5 days

**Weeks 7–8: Advisor Dashboard**
- If `account_type === 'advisor'`, show "Clients" tab (replaces or supplements Portfolio tab).
- Client list with portfolio value summaries, risk profile badges.
- "Add Client" flow: enter email, send invite email via Supabase Edge Function + Resend.
- Client acceptance flow.
- **Effort:** 6 days

**Weeks 9–10: Billing**
- Stripe integration: create-checkout-session Edge Function, webhook handler.
- Subscription management UI in Settings: current plan, upgrade/downgrade, billing portal link.
- Feature flag enforcement (server-side + client-side upgrade prompts).
- Free tier limits enforcement (max positions, max watchlist, AI credit exhaustion message).
- **Effort:** 5 days

**Weeks 11–12: Notifications + Alerts**
- Move price alert checking from browser to Supabase Edge Function on a cron schedule (every 15 minutes during market hours).
- Web Push Notification setup (service worker + VAPID keys).
- Email notifications via Resend for alerts.
- Weekly portfolio digest email (markdown template, send via Edge Function).
- **Effort:** 5 days

**Phase 2 Deliverable:** Full advisor B2B product. Paying users. Price alerts from server.
**Phase 2 Effort Total:** ~21 developer-days (solo dev)

---

### Phase 3 — Advanced Features (Weeks 13–24)

**Goal:** Analytics, compliance features, export, white-labeling.

**Weeks 13–15: Analytics + Reporting**
- Per-user AI query analytics (token usage, cost attribution).
- Advisor: aggregate AUM dashboard, client performance comparison.
- Portfolio performance history (daily snapshot stored in `portfolio_snapshots` table).
- PDF report generation (Edge Function using Puppeteer or a headless PDF service).
- **Effort:** 8 days

**Weeks 16–18: Data Export + Compliance**
- "Export my data" (GDPR portability): full JSON export, CSV per portfolio.
- "Delete my account" flow with 7-day soft delete + hard delete.
- Audit log table for advisor actions (who accessed which client portfolio, when).
- Privacy policy and terms of service pages.
- **Effort:** 6 days

**Weeks 19–21: White-Label**
- Advisor branding: firm name + logo stored in `profiles.firm_name` and a `firm_logo_url`.
- Client-facing view shows advisor's branding.
- Subdomain support (e.g., `smithwealth.mystockanalyst.app`) — requires Cloudflare for DNS, Vercel for routing.
- **Effort:** 7 days

**Weeks 22–24: Performance + Scale**
- Cache layer: add Upstash Redis (Supabase-compatible) for quote caching to reduce Yahoo Finance proxy load.
- Rate limiting on AI proxy Edge Function.
- Load testing, error monitoring (Sentry).
- **Effort:** 6 days

**Phase 3 Deliverable:** Enterprise-ready product with compliance, white-label, and analytics.
**Phase 3 Effort Total:** ~27 developer-days (solo dev)

---

## 10. Technical Integration Points

### 10.1 Parts of `index.html` Requiring Refactoring

The app is ~2,200 lines in a single file. The following sections require changes:

**A. Script section — State initialization (lines ~632–646)**

Current:
```javascript
let apiKey = localStorage.getItem('msa_key') || '';
let portfolio = safeJsonParse('msa_portfolio', {});
let watchlist = safeJsonParse('msa_watchlist', []);
```

Required change: Replace direct localStorage reads with an async `loadAppState()` function that first tries Supabase (if authenticated), falls back to localStorage (if offline or unauthenticated), and resolves conflicts.

**B. `saveSettings()` function (lines ~722–734)**

Currently writes API keys to `localStorage.setItem('msa_key', apiKey)`. Must be redirected to call a Supabase Edge Function that stores keys in Vault. The local variable `apiKey` should be replaced with a flag `hasApiKey: boolean` (never expose the key to client-side JavaScript after storage).

**C. `streamAI()` function (lines ~749–788)**

Currently calls `https://api.anthropic.com/v1/messages` and `https://generativelanguage.googleapis.com/...` directly from the browser, with the key embedded in the request header. Must be replaced with a call to `/api/ai-proxy` Edge Function that:
- Authenticates the caller via the Supabase JWT in the request header.
- Checks and decrements `ai_credits_remaining` for managed-key users.
- Retrieves the user's API key from Vault.
- Proxies the request to Anthropic/Google.
- Returns the streaming response.

**D. `addPosition()`, `removePosition()` (portfolio write functions)**

Add a thin data layer: after each localStorage write, fire an async Supabase upsert:
```javascript
async function syncPositionToCloud(ticker, shares, costBasis) {
  if (!supabase.auth.getUser()) return; // unauthenticated, local-only
  await supabase.from('positions').upsert({
    portfolio_id: getActivePortfolioId(),
    ticker, shares, avg_cost: costBasis,
    updated_at: new Date().toISOString()
  }, { onConflict: 'portfolio_id,ticker' });
}
```

**E. App initialization — add auth state listener**

Add early in the script:
```javascript
supabase.auth.onAuthStateChange(async (event, session) => {
  if (event === 'SIGNED_IN') {
    await migrateLocalDataIfNeeded(session.user);
    await loadCloudState(session.user.id);
    renderAll();
  }
  if (event === 'SIGNED_OUT') {
    // revert to local-only mode
  }
});
```

### 10.2 API Call Changes

**Add auth headers to all Supabase calls:**
Supabase JS SDK handles this automatically when a session is active. The client sends `Authorization: Bearer {jwt}` on every call. RLS policies enforce data ownership server-side.

**AI proxy calls:**
```javascript
const response = await fetch('/api/ai-proxy', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${(await supabase.auth.getSession()).data.session.access_token}`,
  },
  body: JSON.stringify({ provider: 'claude', messages, systemPrompt, maxTokens }),
});
```

**Yahoo Finance calls:** No change required. These are unauthenticated public API calls. No user data is sent to Yahoo Finance.

### 10.3 API Key Storage Migration

**Current (insecure):**
```
localStorage['msa_key'] = 'sk-ant-api03-...'   ← plaintext in browser storage
```

**Target (secure):**
```
Supabase Vault
  └── vault.secrets table
       └── { name: 'anthropic_key_{user_id}', secret: encrypted_value }
            ← encrypted with pgsodium, decryptable only by server
```

**Migration path:**
1. On first sign-in, if `localStorage['msa_key']` exists, show a prompt: "Save your API key securely to your account?" → on confirm, POST to Edge Function → stored in Vault → clear from localStorage.
2. The Edge Function returns only a boolean `has_key: true`, never the key value.
3. The Settings modal field changes from a password input showing the key to a field showing "••••••••••••• (saved securely)" with a "Remove Key" option.

### 10.4 Session Management in PWA Context

**Problem:** PWA standalone windows do not automatically share session state with the browser, and iOS Safari aggressively clears localStorage for installed PWAs in some versions.

**Mitigations:**

1. Use Supabase's built-in session persistence (`persistSession: true` in the client config, which is the default). The SDK stores the JWT and refresh token in localStorage under `sb-{project_ref}-auth-token`.

2. On iOS, test with `WKWebView` session persistence. As of iOS 16.4+, installed PWAs (added to Home Screen) use a persistent storage partition — this is generally stable.

3. Implement a session heartbeat: on every app focus event (`document.addEventListener('visibilitychange', ...)`), call `supabase.auth.getSession()` to silently refresh the token if within 5 minutes of expiry.

4. "Remember this device" is default-on for PWA installs. The refresh token (14-day expiry) keeps the user logged in without re-authenticating on every launch.

5. For a "signed-out offline" edge case (refresh token expired, no connectivity): the app degrades to localStorage-only mode. A non-dismissable banner appears: "You're offline and not signed in — changes won't sync." On connectivity restore, prompt re-authentication.

### 10.5 Refactoring Strategy for the Single-File Architecture

The single-HTML-file architecture is a deliberate choice for PWA simplicity. Phase 1 can preserve this with minimal extraction:

1. Add Supabase SDK via CDN script tag (no build step required).
2. Add a `supabase-client.js` or inline the client initialization near the top of the `<script>` block.
3. Introduce a `data/` module pattern inline (JavaScript module pattern with IIFE) to separate localStorage operations from UI rendering.

For Phase 2 and beyond, consider splitting into:
```
docs/
  index.html          ← shell + tab markup only (~300 lines)
  app.js              ← main logic
  data.js             ← storage layer (localStorage + Supabase)
  auth.js             ← authentication flows
  ai.js               ← AI proxy calls
  manifest.json
  sw.js               ← service worker (add in Phase 1)
```

This split can be done with native ES modules (`<script type="module" src="app.js">`) with no bundler. Given the app is deployed as a static site (GitHub Pages / Vercel), this requires no infrastructure change.

---

## Appendix A — Supabase Quick-Start Configuration

```javascript
// At the top of index.html <script> section
const supabase = window.supabase.createClient(
  'https://YOUR_PROJECT_ID.supabase.co',
  'YOUR_ANON_PUBLIC_KEY',
  {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,  // handles OAuth redirects
    },
    realtime: {
      params: { eventsPerSecond: 2 },
    },
  }
);
```

The `anon` (public) key is safe to embed in client-side code. It is not a secret. RLS policies enforce that users can only access their own data, regardless of knowing the anon key.

---

## Appendix B — Recommended Technology Stack Summary

| Layer | Technology | Rationale |
|---|---|---|
| Database | Supabase PostgreSQL | SQL, RLS, Realtime, free tier |
| Auth | Supabase Auth | Google OAuth, Apple, Magic Link built-in |
| Secret storage | Supabase Vault | Encrypted API key storage |
| Edge Functions | Supabase Edge Functions (Deno) | AI proxy, cron jobs, webhooks |
| Payments | Stripe | Industry standard, excellent Node/Deno SDK |
| Email | Resend | Developer-friendly, 3,000 emails/month free |
| Push notifications | Web Push (VAPID) via service worker | No third-party dependency |
| CDN / Hosting | Vercel or GitHub Pages | Current GitHub Pages deploy path |
| Monitoring | Sentry (free tier) | Error tracking in JS and Edge Functions |

---

## Appendix C — LocalStorage Key Mapping to Cloud Schema

| Current localStorage Key | New Cloud Table | Column(s) | Notes |
|---|---|---|---|
| `msa_portfolio` | `positions` | `portfolio_id, ticker, shares, avg_cost` | Migrate on first sign-in |
| `msa_watchlist` | `watchlist_items` | `user_id, ticker` | Merge on conflict |
| `msa_alerts` | `price_alerts` | `user_id, ticker, condition, target_price` | Migrate on first sign-in |
| `msa_key` | Supabase Vault | `secret` (encrypted) | Never store post-migration |
| `msa_gemini` | Supabase Vault | `secret` (encrypted) | Never store post-migration |
| `msa_ai_pref` | `profiles` | `ai_provider` | Sync to profile |
| `msa_name` | `profiles` | `display_name` | Sync to profile |
| `msa_dark` | localStorage only | — | Device preference, do not sync |
