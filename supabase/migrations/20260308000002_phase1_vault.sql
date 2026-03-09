-- Phase 1: pgcrypto + Supabase Vault setup for secure API key storage
-- Vault allows storing secrets server-side so AI API keys never touch the browser localStorage

-- ════════════════════════════════════════════════════════════
-- EXTENSIONS
-- ════════════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS pgsodium;
CREATE EXTENSION IF NOT EXISTS "supabase_vault" SCHEMA vault;

-- ════════════════════════════════════════════════════════════
-- AI KEY STORAGE TABLE
-- Stores references to Vault secrets (not the keys themselves)
-- The actual encrypted key bytes live in vault.secrets
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.user_api_keys (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  provider     TEXT NOT NULL CHECK (provider IN ('claude', 'gemini')),
  secret_id    UUID NOT NULL,  -- references vault.secrets.id
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, provider)
);

ALTER TABLE public.user_api_keys ENABLE ROW LEVEL SECURITY;

-- Users can only manage their own key references
CREATE POLICY "api_keys_self"
  ON public.user_api_keys FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE TRIGGER user_api_keys_updated_at
  BEFORE UPDATE ON public.user_api_keys
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ════════════════════════════════════════════════════════════
-- HELPER FUNCTIONS (called from Edge Functions, not the browser)
-- ════════════════════════════════════════════════════════════

-- Store or update a user's API key in Vault
-- Called by the ai-proxy Edge Function after the user submits a key
CREATE OR REPLACE FUNCTION public.upsert_user_api_key(
  p_user_id UUID,
  p_provider TEXT,
  p_key_value TEXT
)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, vault AS $$
DECLARE
  v_secret_id UUID;
  v_existing_secret_id UUID;
BEGIN
  -- Check for existing key
  SELECT secret_id INTO v_existing_secret_id
  FROM public.user_api_keys
  WHERE user_id = p_user_id AND provider = p_provider;

  IF v_existing_secret_id IS NOT NULL THEN
    -- Update existing vault secret
    UPDATE vault.secrets
    SET secret = p_key_value,
        updated_at = NOW()
    WHERE id = v_existing_secret_id;
  ELSE
    -- Insert new vault secret
    INSERT INTO vault.secrets (name, secret)
    VALUES (
      format('api_key_%s_%s', p_provider, p_user_id),
      p_key_value
    )
    RETURNING id INTO v_secret_id;

    INSERT INTO public.user_api_keys (user_id, provider, secret_id)
    VALUES (p_user_id, p_provider, v_secret_id);
  END IF;
END;
$$;

-- Retrieve a user's decrypted API key (called from Edge Functions only — never from browser)
CREATE OR REPLACE FUNCTION public.get_user_api_key(
  p_user_id UUID,
  p_provider TEXT
)
RETURNS TEXT
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, vault AS $$
DECLARE
  v_secret_id UUID;
  v_decrypted TEXT;
BEGIN
  SELECT secret_id INTO v_secret_id
  FROM public.user_api_keys
  WHERE user_id = p_user_id AND provider = p_provider;

  IF v_secret_id IS NULL THEN
    RETURN NULL;
  END IF;

  SELECT decrypted_secret INTO v_decrypted
  FROM vault.decrypted_secrets
  WHERE id = v_secret_id;

  RETURN v_decrypted;
END;
$$;

-- ════════════════════════════════════════════════════════════
-- AI CREDIT TRACKING
-- Decrement credits for free-tier users; returns remaining credits
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.consume_ai_credit(p_user_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE
  v_remaining INTEGER;
  v_tier TEXT;
BEGIN
  SELECT subscription_tier, ai_credits_remaining
  INTO v_tier, v_remaining
  FROM public.profiles
  WHERE id = p_user_id;

  -- Pro/advisor tiers have unlimited credits
  IF v_tier != 'free' THEN
    RETURN -1; -- -1 = unlimited
  END IF;

  IF v_remaining <= 0 THEN
    RETURN 0; -- caller should return 402
  END IF;

  UPDATE public.profiles
  SET ai_credits_remaining = ai_credits_remaining - 1,
      updated_at = NOW()
  WHERE id = p_user_id;

  RETURN v_remaining - 1;
END;
$$;
