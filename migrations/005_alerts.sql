-- ── Sprint 3: Alerts + Portfolio Snapshots ────────────────────────────────────

CREATE TABLE IF NOT EXISTS alerts (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  alert_type   text NOT NULL CHECK (alert_type IN (
    'concentration', 'unrealized_loss', 'health_drop',
    'goal_misalignment', 'diversification', 'earnings_upcoming', 'broker_reconnect'
  )),
  ticker       text,
  message      text NOT NULL,
  severity     text DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
  metadata     jsonb DEFAULT '{}',
  is_dismissed boolean DEFAULT false,
  created_at   timestamptz DEFAULT now(),
  dismissed_at timestamptz
);

ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own alerts"
  ON alerts FOR ALL
  USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_alerts_user_active
  ON alerts (user_id, is_dismissed, created_at DESC);


CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  total_value   numeric(16,2) NOT NULL,
  total_cost    numeric(16,2) NOT NULL,
  recorded_date date NOT NULL,
  UNIQUE (user_id, recorded_date)
);

ALTER TABLE portfolio_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own snapshots"
  ON portfolio_snapshots FOR ALL
  USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_snapshots_user_date
  ON portfolio_snapshots (user_id, recorded_date DESC);


-- Helper to record today's snapshot (idempotent via ON CONFLICT)
CREATE OR REPLACE FUNCTION record_portfolio_snapshot(
  p_user_id     uuid,
  p_total_value numeric,
  p_total_cost  numeric
) RETURNS void LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO portfolio_snapshots (user_id, total_value, total_cost, recorded_date)
  VALUES (p_user_id, p_total_value, p_total_cost, CURRENT_DATE)
  ON CONFLICT (user_id, recorded_date)
  DO UPDATE SET total_value = EXCLUDED.total_value,
                total_cost  = EXCLUDED.total_cost;
END;
$$;
