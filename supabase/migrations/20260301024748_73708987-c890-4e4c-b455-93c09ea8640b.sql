
ALTER TABLE public.standardized_processing_runs
ADD COLUMN report_date date,
ADD COLUMN timing text,
ADD COLUMN fiscal_period_end date;
