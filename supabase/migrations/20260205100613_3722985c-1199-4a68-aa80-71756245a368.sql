-- Create excel_processing_runs table for tracking agentic processing status
CREATE TABLE public.excel_processing_runs (
    id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    report_date DATE NOT NULL,
    timing TEXT NOT NULL CHECK (timing IN ('premarket', 'afterhours')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    files_updated INTEGER DEFAULT 0,
    data_sources_used TEXT[] DEFAULT '{}',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Prevent duplicate runs for same ticker/date/timing
    UNIQUE (ticker, report_date, timing)
);

-- Enable Row Level Security
ALTER TABLE public.excel_processing_runs ENABLE ROW LEVEL SECURITY;

-- Create policy for authenticated users to view processing runs
CREATE POLICY "Authenticated users can view processing runs"
ON public.excel_processing_runs
FOR SELECT
USING (true);

-- Create index for faster queries by status and date
CREATE INDEX idx_excel_processing_runs_status ON public.excel_processing_runs(status);
CREATE INDEX idx_excel_processing_runs_report_date ON public.excel_processing_runs(report_date);
CREATE INDEX idx_excel_processing_runs_ticker ON public.excel_processing_runs(ticker);