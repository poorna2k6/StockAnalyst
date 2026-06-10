-- Migration 002: Security hardening
-- Run in Supabase SQL Editor

-- ── Audit log (append-only, tamper-evident) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid,                    -- null for system events
  event_type  text NOT NULL,           -- 'login', 'portfolio_reset', 'account_deleted', etc.
  resource    text,                    -- 'portfolio', 'settings', 'broker_connection'
  metadata    jsonb DEFAULT '{}',      -- context — NEVER include tokens or keys
  ip_hash     text,                    -- SHA-256 of first 3 octets only
  created_at  timestamptz DEFAULT now()
);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
-- Insert-only for all authenticated users; no UPDATE or DELETE makes it tamper-evident
CREATE POLICY "insert audit events" ON audit_log FOR INSERT WITH CHECK (true);
CREATE POLICY "read own audit events" ON audit_log FOR SELECT USING (auth.uid() = user_id);

-- ── Chat history auto-expiry (90 days) ───────────────────────────────────────
-- Call this from a scheduled job (pg_cron on Supabase Pro, or Railway cron).
CREATE OR REPLACE FUNCTION delete_old_chat_history()
RETURNS void
LANGUAGE sql
SECURITY DEFINER
AS $$
  DELETE FROM chat_history WHERE created_at < NOW() - INTERVAL '90 days';
$$;

-- ── Rename BYOK key columns to indicate vault storage (Phase 2 migration) ────
-- Uncomment when Supabase Vault is enabled on your project (Pro plan).
-- ALTER TABLE user_settings RENAME COLUMN byok_claude_key TO byok_claude_key_vault_id;
-- ALTER TABLE user_settings RENAME COLUMN byok_gemini_key TO byok_gemini_key_vault_id;
