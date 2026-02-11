 import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
 
 const corsHeaders = {
   'Access-Control-Allow-Origin': '*',
   'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
 };
 
 // Get current date in Central Time (America/Chicago)
 function getCentralTimeDate(): string {
   const now = new Date();
   const centralTime = new Intl.DateTimeFormat('en-CA', {
     timeZone: 'America/Chicago',
     year: 'numeric',
     month: '2-digit',
     day: '2-digit',
   }).format(now);
   return centralTime; // Returns YYYY-MM-DD format
 }
 
 interface EarningsRecord {
   code: string;
   report_date: string;
   date: string; // fiscal period end
   before_after_market: string | null;
   actual: number | null;
   estimate: number | null;
   difference: number | null;
   percent: number | null;
 }
 
 Deno.serve(async (req) => {
   // Handle CORS preflight
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
 
      // Get date from query param or fall back to Central Time
      const url = new URL(req.url);
      const dateParam = url.searchParams.get('date');
      const currentDate = dateParam || getCentralTimeDate();
     console.log(`Fetching earnings calendar for date: ${currentDate}`);
 
     // Call EODHD API
     const apiUrl = `https://eodhd.com/api/calendar/earnings?from=${currentDate}&to=${currentDate}&api_token=${apiToken}&fmt=json`;
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
           message: 'No US earnings found for today',
           date: currentDate,
           totalRecords: earnings.length,
           usRecords: 0,
           matchedRecords: 0,
         }),
         { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
       );
     }
 
     // Extract tickers (strip .US suffix)
     const tickers = usEarnings.map(e => e.code.replace('.US', ''));
     
     // Query companies table to find matches
     const { data: matchedCompanies, error: queryError } = await supabase
       .from('companies')
       .select('ticker')
       .in('ticker', tickers);
 
     if (queryError) {
       throw new Error(`Database query error: ${queryError.message}`);
     }
 
     const matchedTickers = new Set(matchedCompanies?.map(c => c.ticker) || []);
     console.log(`Found ${matchedTickers.size} matching companies in database`);
 
     if (matchedTickers.size === 0) {
       return new Response(
         JSON.stringify({
           success: true,
           message: 'No matching companies found in database',
           date: currentDate,
           totalRecords: earnings.length,
           usRecords: usEarnings.length,
           matchedRecords: 0,
         }),
         { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
       );
     }
 
     // Prepare records for insertion
     const recordsToInsert = usEarnings
       .filter(e => matchedTickers.has(e.code.replace('.US', '')))
       .map(e => ({
         ticker: e.code.replace('.US', ''),
         report_date: e.report_date || currentDate,
         fiscal_period_end: e.date || null,
         before_after_market: e.before_after_market || null,
         actual_eps: e.actual,
         estimate_eps: e.estimate,
         difference: e.difference,
         percent_surprise: e.percent,
         fetched_at: new Date().toISOString(),
       }));
 
     console.log(`Inserting ${recordsToInsert.length} records into earnings_calendar`);
 
     // Upsert to handle duplicates (when cron runs twice daily)
     const { data: insertedData, error: insertError } = await supabase
       .from('earnings_calendar')
       .upsert(recordsToInsert, {
         onConflict: 'ticker,report_date,before_after_market',
         ignoreDuplicates: false,
       })
       .select();
 
     if (insertError) {
       throw new Error(`Insert error: ${insertError.message}`);
     }
 
     return new Response(
       JSON.stringify({
         success: true,
         message: `Successfully processed earnings calendar`,
         date: currentDate,
         totalRecords: earnings.length,
         usRecords: usEarnings.length,
         matchedRecords: recordsToInsert.length,
         insertedRecords: insertedData?.length || 0,
       }),
       { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
     );
 
   } catch (error) {
     console.error('Error in fetch-earnings-calendar:', error);
     const errorMessage = error instanceof Error ? error.message : 'Unknown error';
     return new Response(
       JSON.stringify({
         success: false,
        error: errorMessage,
       }),
       { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
     );
   }
 });