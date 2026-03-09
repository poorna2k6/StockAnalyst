-- Phase 3: GDPR support — cascade delete function and data export helpers

-- ════════════════════════════════════════════════════════════
-- GDPR CASCADE DELETE
-- Deletes all user data in the correct dependency order,
-- then calls auth.users delete via a signal to the Edge Function.
-- The actual auth.users deletion is done by the delete-account Edge Function
-- using supabase.auth.admin.deleteUser() with the service role key.
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.gdpr_delete_user_data(p_user_id UUID)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
BEGIN
  -- Delete in reverse dependency order to respect FK constraints

  -- Audit logs (no FK cascade, must delete explicitly; this also removes SEC records —
  -- only appropriate once the user has formally invoked GDPR right to erasure)
  DELETE FROM public.audit_logs WHERE user_id = p_user_id;

  -- Portfolio snapshots (via CASCADE on portfolio_id, but be explicit)
  DELETE FROM public.portfolio_snapshots
    WHERE portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = p_user_id);

  -- Collaborator invites sent by this user (as portfolio owner)
  DELETE FROM public.portfolio_collaborators
    WHERE portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = p_user_id);

  -- Collaborator memberships this user accepted (as a collaborator)
  DELETE FROM public.portfolio_collaborators WHERE user_id = p_user_id;

  -- Advisor clients
  DELETE FROM public.advisor_clients WHERE advisor_id = p_user_id;
  DELETE FROM public.advisor_clients WHERE client_id = p_user_id;

  -- Notification preferences
  DELETE FROM public.notification_preferences WHERE user_id = p_user_id;

  -- Advisor branding
  DELETE FROM public.advisor_branding WHERE advisor_id = p_user_id;

  -- Price alerts
  DELETE FROM public.price_alerts WHERE user_id = p_user_id;

  -- Watchlist
  DELETE FROM public.watchlist_items WHERE user_id = p_user_id;

  -- Positions (via CASCADE on portfolio_id)
  DELETE FROM public.positions
    WHERE portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = p_user_id);

  -- Portfolios
  DELETE FROM public.portfolios WHERE owner_id = p_user_id;

  -- User API key references (vault secrets deleted by Edge Function before calling this)
  DELETE FROM public.user_api_keys WHERE user_id = p_user_id;

  -- Profile (must be last — referenced by many tables above)
  DELETE FROM public.profiles WHERE id = p_user_id;

  -- NOTE: auth.users deletion is done by the delete-account Edge Function
  -- using supabase.auth.admin.deleteUser(p_user_id) AFTER this function returns.
END;
$$;

-- ════════════════════════════════════════════════════════════
-- GDPR DATA EXPORT QUERY
-- Returns a structured JSON object with all user data.
-- Called by the data-export Edge Function.
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.gdpr_export_user_data(p_user_id UUID)
RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE
  v_result JSONB;
BEGIN
  SELECT jsonb_build_object(
    'exported_at', NOW(),
    'profile', (SELECT to_jsonb(p) FROM public.profiles p WHERE p.id = p_user_id),
    'portfolios', (
      SELECT jsonb_agg(to_jsonb(p))
      FROM public.portfolios p WHERE p.owner_id = p_user_id
    ),
    'positions', (
      SELECT jsonb_agg(to_jsonb(pos))
      FROM public.positions pos
      WHERE pos.portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = p_user_id)
    ),
    'watchlist', (
      SELECT jsonb_agg(to_jsonb(w))
      FROM public.watchlist_items w WHERE w.user_id = p_user_id
    ),
    'price_alerts', (
      SELECT jsonb_agg(to_jsonb(a))
      FROM public.price_alerts a WHERE a.user_id = p_user_id
    ),
    'portfolio_snapshots', (
      SELECT jsonb_agg(to_jsonb(s))
      FROM public.portfolio_snapshots s
      WHERE s.portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = p_user_id)
    ),
    'audit_logs', (
      SELECT jsonb_agg(jsonb_build_object(
        'id', l.id, 'action', l.action, 'entity_type', l.entity_type,
        'created_at', l.created_at
        -- payload excluded from export for security (may contain API responses)
      ))
      FROM public.audit_logs l WHERE l.user_id = p_user_id
    )
  ) INTO v_result;

  RETURN v_result;
END;
$$;
