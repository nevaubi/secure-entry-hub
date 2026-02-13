
-- Add new columns for Yahoo Finance data
ALTER TABLE public.recurring_premarket_data
  ADD COLUMN dow_symbol text,
  ADD COLUMN dow_name text,
  ADD COLUMN dow_market_time text,
  ADD COLUMN dow_volume text,
  ADD COLUMN dow_open_interest text,
  ADD COLUMN sp500_symbol text,
  ADD COLUMN sp500_name text,
  ADD COLUMN sp500_market_time text,
  ADD COLUMN sp500_volume text,
  ADD COLUMN sp500_open_interest text,
  ADD COLUMN nas_symbol text,
  ADD COLUMN nas_name text,
  ADD COLUMN nas_market_time text,
  ADD COLUMN nas_volume text,
  ADD COLUMN nas_open_interest text;

-- Drop old columns
ALTER TABLE public.recurring_premarket_data
  DROP COLUMN IF EXISTS dow_direction,
  DROP COLUMN IF EXISTS sp500_direction,
  DROP COLUMN IF EXISTS nas_direction,
  DROP COLUMN IF EXISTS last_updated;
