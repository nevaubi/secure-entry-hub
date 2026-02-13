
CREATE TABLE public.recurring_premarket_data (
  id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  captured_at timestamptz NOT NULL DEFAULT now(),
  dow_price numeric,
  dow_change numeric,
  dow_change_pct numeric,
  dow_direction text,
  sp500_price numeric,
  sp500_change numeric,
  sp500_change_pct numeric,
  sp500_direction text,
  nas_price numeric,
  nas_change numeric,
  nas_change_pct numeric,
  nas_direction text,
  last_updated text,
  screenshot_url text,
  raw_gemini_response jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.recurring_premarket_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view premarket data"
  ON public.recurring_premarket_data
  FOR SELECT
  USING (true);
