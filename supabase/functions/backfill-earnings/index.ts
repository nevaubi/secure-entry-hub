import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface EarningsRecord {
  code: string;
  report_date: string;
  date: string;
  before_after_market: string | null;
  actual: number | null;
  estimate: number | null;
  difference: number | null;
  percent: number | null;
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const apiToken = Deno.env.get('EODHD_API_TOKEN');
    if (!apiToken) {
      throw new Error('EODHD_API_TOKEN not configured');
    }

    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Parse optional date range from body
    let fromDate = '2026-01-11';
    let toDate = '2026-02-09';

    if (req.method === 'POST') {
      try {
        const body = await req.json();
        if (body.from_date) fromDate = body.from_date;
        if (body.to_date) toDate = body.to_date;
      } catch {
        // Use defaults
      }
    }

    console.log(`Fetching earnings calendar from ${fromDate} to ${toDate}`);

    const apiUrl = `https://eodhd.com/api/calendar/earnings?from=${fromDate}&to=${toDate}&api_token=${apiToken}&fmt=json`;
    const response = await fetch(apiUrl);

    if (!response.ok) {
      throw new Error(`EODHD API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    const earnings: EarningsRecord[] = data.earnings || [];

    console.log(`Received ${earnings.length} total earnings records from API`);

    // Filter to only .US tickers
    const usEarnings = earnings.filter(e => e.code && e.code.endsWith('.US'));
    console.log(`Filtered to ${usEarnings.length} US tickers`);

    if (usEarnings.length === 0) {
      return new Response(
        JSON.stringify({
          success: true,
          message: 'No US earnings found for this date range',
          from_date: fromDate,
          to_date: toDate,
          totalRecords: earnings.length,
          usRecords: 0,
          matchedRecords: 0,
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Extract unique tickers (strip .US suffix)
    const tickers = [...new Set(usEarnings.map(e => e.code.replace('.US', '')))];

    // Query companies table in batches of 500 to avoid limits
    const allMatchedTickers = new Set<string>();
    for (let i = 0; i < tickers.length; i += 500) {
      const batch = tickers.slice(i, i + 500);
      const { data: matchedCompanies, error: queryError } = await supabase
        .from('companies')
        .select('ticker')
        .in('ticker', batch);

      if (queryError) {
        throw new Error(`Database query error: ${queryError.message}`);
      }

      matchedCompanies?.forEach(c => allMatchedTickers.add(c.ticker));
    }

    console.log(`Found ${allMatchedTickers.size} matching companies in database`);

    if (allMatchedTickers.size === 0) {
      return new Response(
        JSON.stringify({
          success: true,
          message: 'No matching companies found in database',
          from_date: fromDate,
          to_date: toDate,
          totalRecords: earnings.length,
          usRecords: usEarnings.length,
          matchedRecords: 0,
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Prepare records for insertion
    const recordsToInsert = usEarnings
      .filter(e => allMatchedTickers.has(e.code.replace('.US', '')))
      .map(e => ({
        ticker: e.code.replace('.US', ''),
        report_date: e.report_date,
        fiscal_period_end: e.date || null,
        before_after_market: e.before_after_market || null,
        actual_eps: e.actual,
        estimate_eps: e.estimate,
        difference: e.difference,
        percent_surprise: e.percent,
        fetched_at: new Date().toISOString(),
      }));

    console.log(`Upserting ${recordsToInsert.length} records into earnings_calendar`);

    // Upsert in batches of 200
    let totalInserted = 0;
    for (let i = 0; i < recordsToInsert.length; i += 200) {
      const batch = recordsToInsert.slice(i, i + 200);
      const { data: insertedData, error: insertError } = await supabase
        .from('earnings_calendar')
        .upsert(batch, {
          onConflict: 'ticker,report_date,before_after_market',
          ignoreDuplicates: false,
        })
        .select();

      if (insertError) {
        throw new Error(`Insert error (batch ${i}): ${insertError.message}`);
      }

      totalInserted += insertedData?.length || 0;
    }

    return new Response(
      JSON.stringify({
        success: true,
        message: `Successfully backfilled earnings calendar`,
        from_date: fromDate,
        to_date: toDate,
        totalRecords: earnings.length,
        usRecords: usEarnings.length,
        matchedRecords: recordsToInsert.length,
        insertedRecords: totalInserted,
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error('Error in backfill-earnings:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return new Response(
      JSON.stringify({ success: false, error: errorMessage }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
