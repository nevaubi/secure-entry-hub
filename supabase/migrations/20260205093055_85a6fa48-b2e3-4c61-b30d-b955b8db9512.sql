-- Create table to track file processing status for each ticker
CREATE TABLE public.earnings_file_processing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  report_date DATE NOT NULL,
  bucket_name TEXT NOT NULL,
  file_exists BOOLEAN DEFAULT false,
  file_size_bytes INTEGER,
  processed_at TIMESTAMPTZ,
  status TEXT DEFAULT 'pending',
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(ticker, report_date, bucket_name)
);

-- Enable RLS
ALTER TABLE public.earnings_file_processing ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to view processing status
CREATE POLICY "Authenticated users can view processing status"
  ON public.earnings_file_processing
  FOR SELECT
  TO authenticated
  USING (true);