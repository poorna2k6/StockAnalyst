-- ── Sprint 1: Investor Profile ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS investor_profiles (
  user_id                  uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
  age_range                text,
  investment_horizon_years int,
  primary_goal             text CHECK (primary_goal IN (
    'retirement', 'wealth_accumulation', 'income', 'capital_preservation', 'speculation'
  )),
  risk_tolerance           text CHECK (risk_tolerance IN ('conservative', 'moderate', 'aggressive')),
  risk_score               int CHECK (risk_score BETWEEN 1 AND 10),
  annual_income_range      text,
  tax_sensitive            boolean DEFAULT false,
  investment_experience    text CHECK (investment_experience IN ('beginner', 'intermediate', 'experienced')),
  sectors_to_avoid         text[] DEFAULT '{}',
  max_single_position_pct  numeric DEFAULT 20.0,
  preferred_advice_style   text DEFAULT 'concise',
  profile_completed_at     timestamptz,
  created_at               timestamptz DEFAULT now(),
  updated_at               timestamptz DEFAULT now()
);

ALTER TABLE investor_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own profile"
  ON investor_profiles FOR ALL
  USING (auth.uid() = user_id);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_investor_profile_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_investor_profile_updated_at
  BEFORE UPDATE ON investor_profiles
  FOR EACH ROW EXECUTE FUNCTION update_investor_profile_updated_at();
