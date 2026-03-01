
CREATE TABLE public.standardized_processing_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  files_updated INTEGER DEFAULT 0,
  data_sources_used TEXT[] DEFAULT '{}'::text[],
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.standardized_processing_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view standardized runs"
ON public.standardized_processing_runs
FOR SELECT
USING (true);

CREATE POLICY "Authenticated users can update standardized runs"
ON public.standardized_processing_runs
FOR UPDATE
USING (true)
WITH CHECK (true);

CREATE POLICY "Authenticated users can delete standardized runs"
ON public.standardized_processing_runs
FOR DELETE
USING (true);
