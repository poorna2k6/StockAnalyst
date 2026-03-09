-- Phase 1: Core tables, RLS policies, and auto-profile trigger
-- Run via: npx supabase db push

-- ════════════════════════════════════════════════════════════
-- EXTENSIONS
-- ════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ════════════════════════════════════════════════════════════
-- TABLES
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.profiles (
  id                   UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email                TEXT UNIQUE NOT NULL,
  display_name         TEXT,
  avatar_url           TEXT,
  account_type         TEXT NOT NULL DEFAULT 'retail'
                         CHECK (account_type IN ('retail', 'advisor')),
  subscription_tier    TEXT NOT NULL DEFAULT 'free'
                         CHECK (subscription_tier IN ('free', 'pro', 'advisor')),
  subscription_status  TEXT DEFAULT 'active',
  ai_provider          TEXT DEFAULT 'auto'
                         CHECK (ai_provider IN ('auto', 'claude', 'gemini')),
  ai_credits_remaining INTEGER DEFAULT 50,
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  updated_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.portfolios (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id     UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  name         TEXT NOT NULL DEFAULT 'My Portfolio',
  cash_balance NUMERIC(18,2) DEFAULT 0,
  is_default   BOOLEAN DEFAULT FALSE,
  sort_order   INTEGER DEFAULT 0,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.positions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id UUID NOT NULL REFERENCES public.portfolios(id) ON DELETE CASCADE,
  ticker       TEXT NOT NULL,
  shares       NUMERIC(18,6) NOT NULL CHECK (shares > 0),
  avg_cost     NUMERIC(18,4) NOT NULL CHECK (avg_cost > 0),
  added_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (portfolio_id, ticker)
);

CREATE TABLE IF NOT EXISTS public.watchlist_items (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  ticker     TEXT NOT NULL,
  sort_order INTEGER DEFAULT 0,
  added_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS public.price_alerts (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  ticker       TEXT NOT NULL,
  condition    TEXT NOT NULL CHECK (condition IN ('above', 'below')),
  target_price NUMERIC(18,4) NOT NULL,
  is_active    BOOLEAN DEFAULT TRUE,
  triggered_at TIMESTAMPTZ,
  last_fired_at TIMESTAMPTZ,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY
-- ════════════════════════════════════════════════════════════

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.watchlist_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.price_alerts ENABLE ROW LEVEL SECURITY;

-- profiles: user can read and write only their own row
CREATE POLICY "profiles_self"
  ON public.profiles FOR ALL
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- portfolios: owner full access
CREATE POLICY "portfolios_owner"
  ON public.portfolios FOR ALL
  USING (auth.uid() = owner_id)
  WITH CHECK (auth.uid() = owner_id);

-- positions: accessible only through portfolios the user owns
CREATE POLICY "positions_owner"
  ON public.positions FOR ALL
  USING (
    portfolio_id IN (
      SELECT id FROM public.portfolios WHERE owner_id = auth.uid()
    )
  )
  WITH CHECK (
    portfolio_id IN (
      SELECT id FROM public.portfolios WHERE owner_id = auth.uid()
    )
  );

-- watchlist: user can only access their own entries
CREATE POLICY "watchlist_self"
  ON public.watchlist_items FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- price alerts: user can only access their own alerts
CREATE POLICY "alerts_self"
  ON public.price_alerts FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- ════════════════════════════════════════════════════════════
-- AUTO-PROFILE TRIGGER
-- Creates a profiles row + default portfolio on new auth.users insert
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE
  v_portfolio_id UUID;
BEGIN
  INSERT INTO public.profiles (id, email, display_name, avatar_url)
  VALUES (
    NEW.id,
    NEW.email,
    NEW.raw_user_meta_data->>'full_name',
    NEW.raw_user_meta_data->>'avatar_url'
  );

  INSERT INTO public.portfolios (owner_id, name, is_default)
  VALUES (NEW.id, 'My Portfolio', TRUE)
  RETURNING id INTO v_portfolio_id;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ════════════════════════════════════════════════════════════
-- UPDATED_AT AUTO-UPDATE
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER profiles_updated_at   BEFORE UPDATE ON public.profiles   FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER portfolios_updated_at BEFORE UPDATE ON public.portfolios FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER positions_updated_at  BEFORE UPDATE ON public.positions  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
