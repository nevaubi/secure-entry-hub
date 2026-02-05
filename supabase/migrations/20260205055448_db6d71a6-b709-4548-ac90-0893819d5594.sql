-- Create the companies table with ticker as primary key
CREATE TABLE public.companies (
  ticker TEXT PRIMARY KEY,
  company_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  cik INTEGER,
  exchange TEXT,
  sector TEXT,
  description TEXT,
  year_founded INTEGER,
  logo_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;

-- Create policy for authenticated users to read data
CREATE POLICY "Authenticated users can view companies"
ON public.companies
FOR SELECT
TO authenticated
USING (true);

-- Create index on company_id for faster lookups
CREATE INDEX idx_companies_company_id ON public.companies (company_id);

-- Create index on sector for filtering
CREATE INDEX idx_companies_sector ON public.companies (sector);

-- Create index on exchange for filtering
CREATE INDEX idx_companies_exchange ON public.companies (exchange);