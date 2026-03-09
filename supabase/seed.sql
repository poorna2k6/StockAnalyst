-- Dev seed data — only for local Supabase development
-- Applied by: npx supabase db reset

-- Insert a test user profile (auth.users row must exist first — created by supabase CLI in dev)
-- In practice the trigger auto-creates profiles; this seed is for manual/integration test use

-- Demo watchlist items for the test user (inserted after profile exists)
-- These are referenced in integration tests via the fixed test user UUID
DO $$
DECLARE
  v_user_id UUID := '00000000-0000-0000-0000-000000000001';
  v_portfolio_id UUID;
BEGIN
  -- Only insert if the demo user exists
  IF EXISTS (SELECT 1 FROM public.profiles WHERE id = v_user_id) THEN

    SELECT id INTO v_portfolio_id
    FROM public.portfolios
    WHERE owner_id = v_user_id AND is_default = TRUE;

    -- Seed positions
    INSERT INTO public.positions (portfolio_id, ticker, shares, avg_cost)
    VALUES
      (v_portfolio_id, 'AAPL', 10, 150.00),
      (v_portfolio_id, 'MSFT', 5, 300.00),
      (v_portfolio_id, 'NVDA', 8, 500.00)
    ON CONFLICT (portfolio_id, ticker) DO NOTHING;

    -- Seed watchlist
    INSERT INTO public.watchlist_items (user_id, ticker, sort_order)
    VALUES
      (v_user_id, 'TSLA', 0),
      (v_user_id, 'AMZN', 1),
      (v_user_id, 'META', 2)
    ON CONFLICT (user_id, ticker) DO NOTHING;

    -- Seed a price alert
    INSERT INTO public.price_alerts (user_id, ticker, condition, target_price)
    VALUES (v_user_id, 'AAPL', 'above', 200.00)
    ON CONFLICT DO NOTHING;

  END IF;
END $$;
