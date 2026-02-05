-- Create earnings_calendar table
CREATE TABLE public.earnings_calendar (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  ticker TEXT NOT NULL,
  report_date DATE NOT NULL,
  fiscal_period_end DATE,
  before_after_market TEXT,
  actual_eps NUMERIC,
  estimate_eps NUMERIC,
  difference NUMERIC,
  percent_surprise NUMERIC,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- Unique constraint to prevent duplicates when cron runs twice daily
  CONSTRAINT earnings_calendar_unique UNIQUE (ticker, report_date, before_after_market)
);

-- Enable Row Level Security
ALTER TABLE public.earnings_calendar ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Authenticated users can read records
CREATE POLICY "Authenticated users can view earnings calendar"
ON public.earnings_calendar
FOR SELECT
TO authenticated
USING (true);

-- Create index on report_date for efficient querying
CREATE INDEX idx_earnings_calendar_report_date ON public.earnings_calendar(report_date);

-- Create index on ticker for efficient lookups
CREATE INDEX idx_earnings_calendar_ticker ON public.earnings_calendar(ticker);

-- Enable pg_cron extension for scheduled jobs
CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;

-- Enable pg_net extension for HTTP calls from cron
CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;

-- Grant usage on cron schema to postgres role
GRANT USAGE ON SCHEMA cron TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA cron TO postgres;