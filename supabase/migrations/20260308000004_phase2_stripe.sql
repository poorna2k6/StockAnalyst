-- Phase 2: Stripe billing columns and subscription management

-- Add Stripe-related columns to profiles
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS stripe_customer_id     TEXT,
  ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT,
  ADD COLUMN IF NOT EXISTS advisor_seat_limit      INTEGER DEFAULT 10;

-- Index for Stripe customer lookup (used by webhook handler)
CREATE INDEX IF NOT EXISTS profiles_stripe_customer_idx
  ON public.profiles(stripe_customer_id)
  WHERE stripe_customer_id IS NOT NULL;

-- ════════════════════════════════════════════════════════════
-- HELPER: Update subscription state from Stripe webhook
-- Called by the stripe-webhook Edge Function (service role)
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.update_subscription_from_stripe(
  p_stripe_customer_id  TEXT,
  p_subscription_id     TEXT,
  p_tier                TEXT,   -- 'free', 'pro', 'advisor'
  p_status              TEXT    -- 'active', 'canceled', 'past_due', etc.
)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
BEGIN
  UPDATE public.profiles
  SET stripe_subscription_id = p_subscription_id,
      subscription_tier      = p_tier,
      subscription_status    = p_status,
      updated_at             = NOW()
  WHERE stripe_customer_id = p_stripe_customer_id;
END;
$$;

-- ════════════════════════════════════════════════════════════
-- HELPER: Check advisor seat availability
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.advisor_seats_available(p_advisor_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE
  v_limit INTEGER;
  v_used  INTEGER;
BEGIN
  SELECT advisor_seat_limit INTO v_limit FROM public.profiles WHERE id = p_advisor_id;
  SELECT COUNT(*) INTO v_used FROM public.advisor_clients WHERE advisor_id = p_advisor_id;
  RETURN GREATEST(0, COALESCE(v_limit, 10) - v_used);
END;
$$;
