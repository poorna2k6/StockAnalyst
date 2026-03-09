-- Phase 3: Portfolio snapshots, audit logs, and advisor branding

-- ════════════════════════════════════════════════════════════
-- PORTFOLIO SNAPSHOTS (daily performance tracking)
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.portfolio_snapshots (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id    UUID NOT NULL REFERENCES public.portfolios(id) ON DELETE CASCADE,
  snapshot_date   DATE NOT NULL,
  total_value     NUMERIC(18,2),
  total_cost      NUMERIC(18,2),
  positions_json  JSONB,       -- Point-in-time snapshot of all positions
  benchmark_spy   NUMERIC(12,6), -- SPY close price at this date for comparison
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (portfolio_id, snapshot_date)
);

-- ════════════════════════════════════════════════════════════
-- AUDIT LOGS (SEC Rule 204-2 compliance + GDPR accountability)
-- INTENTIONALLY IMMUTABLE: no UPDATE or DELETE policies
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.audit_logs (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES public.profiles(id),
  advisor_id   UUID REFERENCES public.profiles(id),
  action       TEXT NOT NULL,         -- e.g. 'ai_recommendation', 'pdf_report', 'login'
  entity_type  TEXT NOT NULL,         -- e.g. 'recommendation_record', 'portfolio', 'alert'
  entity_id    UUID,
  payload      JSONB,                 -- Full request/response for compliance records
  client_ip    INET,
  user_agent   TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════
-- ADVISOR BRANDING (white-label support)
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.advisor_branding (
  advisor_id       UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
  firm_name        TEXT,
  logo_url         TEXT,
  primary_color    TEXT DEFAULT '#1d4ed8',
  secondary_color  TEXT DEFAULT '#6d28d9',
  custom_domain    TEXT UNIQUE,
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY
-- ════════════════════════════════════════════════════════════

ALTER TABLE public.portfolio_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.advisor_branding ENABLE ROW LEVEL SECURITY;

-- Snapshots: user can only read/write their own portfolio snapshots
CREATE POLICY "snapshots_owner"
  ON public.portfolio_snapshots FOR ALL
  USING (
    portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = auth.uid())
  )
  WITH CHECK (
    portfolio_id IN (SELECT id FROM public.portfolios WHERE owner_id = auth.uid())
  );

-- Audit logs: users can SELECT their own logs, but no UPDATE/DELETE (immutable)
CREATE POLICY "audit_read_self"
  ON public.audit_logs FOR SELECT
  USING (user_id = auth.uid());

-- Advisors can also see logs for their clients
CREATE POLICY "audit_read_advisor"
  ON public.audit_logs FOR SELECT
  USING (advisor_id = auth.uid());

-- Only service role can INSERT audit logs (Edge Functions use service role key)
-- No UPDATE or DELETE policy intentionally — audit logs are immutable

-- Branding: advisor manages their own
CREATE POLICY "branding_self"
  ON public.advisor_branding FOR ALL
  USING (advisor_id = auth.uid())
  WITH CHECK (advisor_id = auth.uid());

-- ════════════════════════════════════════════════════════════
-- HELPER: Write an audit log entry (called from Edge Functions)
-- ════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.write_audit_log(
  p_user_id     UUID,
  p_advisor_id  UUID,
  p_action      TEXT,
  p_entity_type TEXT,
  p_entity_id   UUID,
  p_payload     JSONB,
  p_client_ip   TEXT DEFAULT NULL,
  p_user_agent  TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE
  v_id UUID;
BEGIN
  INSERT INTO public.audit_logs (user_id, advisor_id, action, entity_type, entity_id, payload, client_ip, user_agent)
  VALUES (p_user_id, p_advisor_id, p_action, p_entity_type, p_entity_id, p_payload,
          p_client_ip::INET, p_user_agent)
  RETURNING id INTO v_id;
  RETURN v_id;
END;
$$;
