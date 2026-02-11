
-- 1. rolling_market_news (no ticker column)
CREATE TABLE public.rolling_market_news (
  id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  title text NOT NULL,
  source text NOT NULL,
  published_at timestamptz NOT NULL,
  url text NOT NULL,
  category text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT rolling_market_news_url_key UNIQUE (url)
);

ALTER TABLE public.rolling_market_news ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view market news"
  ON public.rolling_market_news FOR SELECT
  USING (true);

-- 2. rolling_stock_news (has ticker)
CREATE TABLE public.rolling_stock_news (
  id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  title text NOT NULL,
  source text NOT NULL,
  published_at timestamptz NOT NULL,
  url text NOT NULL,
  category text NOT NULL,
  ticker text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT rolling_stock_news_url_key UNIQUE (url)
);

ALTER TABLE public.rolling_stock_news ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view stock news"
  ON public.rolling_stock_news FOR SELECT
  USING (true);

-- 3. rolling_etf_news (has ticker)
CREATE TABLE public.rolling_etf_news (
  id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  title text NOT NULL,
  source text NOT NULL,
  published_at timestamptz NOT NULL,
  url text NOT NULL,
  category text NOT NULL,
  ticker text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT rolling_etf_news_url_key UNIQUE (url)
);

ALTER TABLE public.rolling_etf_news ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view etf news"
  ON public.rolling_etf_news FOR SELECT
  USING (true);

-- 4. rolling_crypto_news (has ticker)
CREATE TABLE public.rolling_crypto_news (
  id uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  title text NOT NULL,
  source text NOT NULL,
  published_at timestamptz NOT NULL,
  url text NOT NULL,
  category text NOT NULL,
  ticker text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT rolling_crypto_news_url_key UNIQUE (url)
);

ALTER TABLE public.rolling_crypto_news ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view crypto news"
  ON public.rolling_crypto_news FOR SELECT
  USING (true);
