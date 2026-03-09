-- Phase 2: Multi-portfolio, advisor features, portfolio sharing, and notification preferences

-- ════════════════════════════════════════════════════════════
-- PORTFOLIO COLLABORATORS (sharing)
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.portfolio_collaborators (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id   UUID NOT NULL REFERENCES public.portfolios(id) ON DELETE CASCADE,
  user_id        UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  invited_email  TEXT,
  role           TEXT NOT NULL DEFAULT 'viewer'
                   CHECK (role IN ('viewer', 'editor')),
  invite_token   TEXT UNIQUE DEFAULT gen_random_uuid()::TEXT,
  accepted_at    TIMESTAMPTZ,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT collaborator_has_identity CHECK (user_id IS NOT NULL OR invited_email IS NOT NULL)
);

-- ════════════════════════════════════════════════════════════
-- ADVISOR CLIENTS
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.advisor_clients (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  advisor_id           UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  client_id            UUID REFERENCES public.profiles(id),
  client_name          TEXT,
  client_email         TEXT,
  assigned_portfolios  UUID[] DEFAULT '{}',
  seat_number          INTEGER NOT NULL,
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (advisor_id, seat_number)
);

-- ════════════════════════════════════════════════════════════
-- NOTIFICATION PREFERENCES
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.notification_preferences (
  user_id            UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
  push_enabled       BOOLEAN DEFAULT FALSE,
  push_subscription  JSONB,        -- Web Push PushSubscription JSON object
  email_digest       TEXT DEFAULT 'weekly'
                       CHECK (email_digest IN ('never', 'daily', 'weekly')),
  alert_delivery     TEXT DEFAULT 'push'
                       CHECK (alert_delivery IN ('push', 'email', 'both'))
);

-- ════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY
-- ════════════════════════════════════════════════════════════

ALTER TABLE public.portfolio_collaborators ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.advisor_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_preferences ENABLE ROW LEVEL SECURITY;

-- Collaborators: portfolio owner or the collaborator themselves
CREATE POLICY "collabs_owner_or_member"
  ON public.portfolio_collaborators FOR ALL
  USING (
    portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = auth.uid())
    OR user_id = auth.uid()
  );

-- Advisor clients: only the advisor
CREATE POLICY "advisor_clients_self"
  ON public.advisor_clients FOR ALL
  USING (advisor_id = auth.uid())
  WITH CHECK (advisor_id = auth.uid());

-- Notification preferences: only the user
CREATE POLICY "notification_prefs_self"
  ON public.notification_preferences FOR ALL
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ════════════════════════════════════════════════════════════
-- UPDATE POSITIONS RLS TO ALLOW COLLABORATOR READ ACCESS
-- ════════════════════════════════════════════════════════════

-- Drop the Phase 1 owner-only policy and replace with owner+collaborator
DROP POLICY IF EXISTS "positions_owner" ON public.positions;

CREATE POLICY "positions_owner_or_collab"
  ON public.positions FOR SELECT
  USING (
    portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = auth.uid())
    OR portfolio_id IN (
      SELECT portfolio_id FROM public.portfolio_collaborators
      WHERE user_id = auth.uid() AND accepted_at IS NOT NULL
    )
  );

-- Writes (INSERT/UPDATE/DELETE) remain owner+editor only
CREATE POLICY "positions_write_owner_or_editor"
  ON public.positions FOR INSERT
  WITH CHECK (
    portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = auth.uid())
    OR portfolio_id IN (
      SELECT portfolio_id FROM public.portfolio_collaborators
      WHERE user_id = auth.uid() AND role = 'editor' AND accepted_at IS NOT NULL
    )
  );

CREATE POLICY "positions_update_owner_or_editor"
  ON public.positions FOR UPDATE
  USING (
    portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = auth.uid())
    OR portfolio_id IN (
      SELECT portfolio_id FROM public.portfolio_collaborators
      WHERE user_id = auth.uid() AND role = 'editor' AND accepted_at IS NOT NULL
    )
  );

CREATE POLICY "positions_delete_owner_or_editor"
  ON public.positions FOR DELETE
  USING (
    portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = auth.uid())
    OR portfolio_id IN (
      SELECT portfolio_id FROM public.portfolio_collaborators
      WHERE user_id = auth.uid() AND role = 'editor' AND accepted_at IS NOT NULL
    )
  );

-- ════════════════════════════════════════════════════════════
-- HELPER: Accept a portfolio invite by token
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.accept_portfolio_invite(p_token TEXT)
RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE
  v_collab RECORD;
BEGIN
  SELECT * INTO v_collab
  FROM public.portfolio_collaborators
  WHERE invite_token = p_token AND accepted_at IS NULL;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('error', 'Invite not found or already accepted');
  END IF;

  UPDATE public.portfolio_collaborators
  SET user_id = auth.uid(),
      accepted_at = NOW()
  WHERE id = v_collab.id;

  RETURN jsonb_build_object('portfolio_id', v_collab.portfolio_id, 'role', v_collab.role);
END;
$$;
