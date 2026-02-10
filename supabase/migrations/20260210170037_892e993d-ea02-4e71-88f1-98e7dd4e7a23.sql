
CREATE POLICY "Authenticated users can update processing runs"
  ON public.excel_processing_runs FOR UPDATE
  TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated users can delete processing runs"
  ON public.excel_processing_runs FOR DELETE
  TO authenticated USING (true);
