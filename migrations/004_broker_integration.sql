-- ── Sprint 2: Broker Integration (SnapTrade) ─────────────────────────────────

CREATE TABLE IF NOT EXISTS broker_connections (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  snaptrade_user_id     text NOT NULL,
  snaptrade_user_secret text NOT NULL,
  authorization_id      text NOT NULL,
  brokerage_slug        text NOT NULL,
  brokerage_name        text,
  account_id            text NOT NULL,
  account_name          text,
  account_type          text,
  account_number_masked text,
  status                text DEFAULT 'active',
  last_sync_at          timestamptz,
  last_sync_error       text,
  sync_enabled          boolean DEFAULT true,
  created_at            timestamptz DEFAULT now(),
  UNIQUE (user_id, authorization_id, account_id)
);

ALTER TABLE broker_connections ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own broker connections"
  ON broker_connections FOR ALL
  USING (auth.uid() = user_id);


CREATE TABLE IF NOT EXISTS imported_holdings (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id          uuid REFERENCES broker_connections ON DELETE CASCADE NOT NULL,
  user_id                uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  ticker                 text NOT NULL,
  name                   text,
  security_type          text,
  units                  numeric(16,6) NOT NULL,
  average_purchase_price numeric(14,4),
  currency               text DEFAULT 'USD',
  current_price          numeric(14,4),
  market_value           numeric(16,2),
  synced_at              timestamptz DEFAULT now(),
  UNIQUE (connection_id, ticker)
);

ALTER TABLE imported_holdings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own imported holdings"
  ON imported_holdings FOR ALL
  USING (auth.uid() = user_id);


CREATE TABLE IF NOT EXISTS sync_jobs (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id  uuid REFERENCES broker_connections ON DELETE CASCADE,
  user_id        uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  job_type       text DEFAULT 'scheduled',
  status         text DEFAULT 'pending',
  holdings_count int,
  error_message  text,
  started_at     timestamptz DEFAULT now(),
  finished_at    timestamptz
);

ALTER TABLE sync_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own sync jobs"
  ON sync_jobs FOR ALL
  USING (auth.uid() = user_id);
