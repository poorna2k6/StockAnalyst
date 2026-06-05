-- ============================================================
-- AI Stock Analyst — Supabase Schema
-- Run this in your Supabase project: SQL Editor → New query
-- ============================================================

-- User settings (model preference, BYOK API keys, credits)
CREATE TABLE IF NOT EXISTS user_settings (
  user_id      uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
  preferred_model   text DEFAULT 'claude' CHECK (preferred_model IN ('claude', 'gemini')),
  byok_claude_key   text,
  byok_gemini_key   text,
  use_byok          boolean DEFAULT false,
  credit_balance    numeric(12, 6) DEFAULT 0,
  updated_at        timestamptz DEFAULT now()
);

-- Portfolio (one per user)
CREATE TABLE IF NOT EXISTS portfolios (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL UNIQUE,
  cash       numeric(14, 2) DEFAULT 0,
  updated_at timestamptz DEFAULT now()
);

-- Positions
CREATE TABLE IF NOT EXISTS positions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id uuid REFERENCES portfolios ON DELETE CASCADE NOT NULL,
  ticker       text NOT NULL,
  shares       numeric(16, 6) NOT NULL,
  avg_cost     numeric(14, 4) NOT NULL,
  added_at     timestamptz DEFAULT now(),
  UNIQUE (portfolio_id, ticker)
);

-- Watchlist
CREATE TABLE IF NOT EXISTS watchlists (
  user_id   uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  ticker    text NOT NULL,
  added_at  timestamptz DEFAULT now(),
  PRIMARY KEY (user_id, ticker)
);

-- Chat history
CREATE TABLE IF NOT EXISTS chat_history (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  session_id text NOT NULL DEFAULT 'default',
  role       text NOT NULL CHECK (role IN ('user', 'assistant')),
  content    text NOT NULL,
  model      text,
  created_at timestamptz DEFAULT now()
);

-- Token usage / spend tracking
CREATE TABLE IF NOT EXISTS token_usage (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  feature       text NOT NULL,
  model         text NOT NULL,
  input_tokens  int DEFAULT 0,
  output_tokens int DEFAULT 0,
  cost_usd      numeric(12, 8) DEFAULT 0,
  was_byok      boolean DEFAULT false,
  created_at    timestamptz DEFAULT now()
);

-- ── Row Level Security ────────────────────────────────────────────────────────

ALTER TABLE user_settings  ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolios     ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlists     ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history   ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_usage    ENABLE ROW LEVEL SECURITY;

-- user_settings: own row only
CREATE POLICY "own settings" ON user_settings
  FOR ALL USING (auth.uid() = user_id);

-- portfolios: own row only
CREATE POLICY "own portfolio" ON portfolios
  FOR ALL USING (auth.uid() = user_id);

-- positions: via portfolio ownership
CREATE POLICY "own positions" ON positions
  FOR ALL USING (
    portfolio_id IN (
      SELECT id FROM portfolios WHERE user_id = auth.uid()
    )
  );

-- watchlists: own rows
CREATE POLICY "own watchlist" ON watchlists
  FOR ALL USING (auth.uid() = user_id);

-- chat_history: own rows
CREATE POLICY "own chat" ON chat_history
  FOR ALL USING (auth.uid() = user_id);

-- token_usage: own rows
CREATE POLICY "own usage" ON token_usage
  FOR ALL USING (auth.uid() = user_id);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions (portfolio_id);
CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history (user_id, session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_token_usage_user ON token_usage (user_id, created_at);
