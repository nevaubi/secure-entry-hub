 const corsHeaders = {
   'Access-Control-Allow-Origin': '*',
   'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
 };
 
 interface EarningsRecord {
   ticker: string;
   report_date: string;
   before_after_market: string | null;
 }
 
 interface TickerPayload {
   ticker: string;
   report_date: string;
   timing: 'premarket' | 'afterhours';
 }
 
 Deno.serve(async (req) => {
   if (req.method === 'OPTIONS') {
     return new Response(null, { headers: corsHeaders });
   }
 
   try {
     const { timing, modal_endpoint } = await req.json();
 
     if (!timing || !['premarket', 'afterhours'].includes(timing)) {
       return new Response(
         JSON.stringify({ success: false, error: 'Invalid timing parameter' }),
         { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
       );
     }
 
     const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
     const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
     const modalWebhookSecret = Deno.env.get('MODAL_WEBHOOK_SECRET');
 
     if (!modalWebhookSecret) {
       return new Response(
         JSON.stringify({ success: false, error: 'MODAL_WEBHOOK_SECRET not configured' }),
         { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
       );
     }
 
     // Get today's date in YYYY-MM-DD format
     const today = new Date().toISOString().split('T')[0];
 
     // Map timing to before_after_market values
     const marketTiming = timing === 'premarket' ? 'Before Market' : 'After Market';
 
     console.log(`Querying earnings for ${today} with timing: ${marketTiming}`);
 
     // Query earnings_calendar for today's tickers
     const earningsResponse = await fetch(
       `${supabaseUrl}/rest/v1/earnings_calendar?report_date=eq.${today}&before_after_market=eq.${encodeURIComponent(marketTiming)}&select=ticker,report_date,before_after_market`,
       {
         headers: {
           'apikey': supabaseKey,
           'Authorization': `Bearer ${supabaseKey}`,
         },
       }
     );
 
     if (!earningsResponse.ok) {
       throw new Error(`Failed to query earnings_calendar: ${earningsResponse.statusText}`);
     }
 
     const earnings: EarningsRecord[] = await earningsResponse.json();
     console.log(`Found ${earnings.length} tickers for processing`);
 
     if (earnings.length === 0) {
       return new Response(
         JSON.stringify({ 
           success: true, 
           message: 'No tickers to process for this timing',
           tickers_count: 0 
         }),
         { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
       );
     }
 
     // Prepare payload for Modal
     const tickerPayloads: TickerPayload[] = earnings.map(e => ({
       ticker: e.ticker,
       report_date: e.report_date,
       timing: timing as 'premarket' | 'afterhours',
     }));
 
     // Create processing run records in the database
     for (const payload of tickerPayloads) {
       const insertResponse = await fetch(
         `${supabaseUrl}/rest/v1/excel_processing_runs`,
         {
           method: 'POST',
           headers: {
             'apikey': supabaseKey,
             'Authorization': `Bearer ${supabaseKey}`,
             'Content-Type': 'application/json',
             'Prefer': 'return=minimal',
           },
           body: JSON.stringify({
             ticker: payload.ticker,
             report_date: payload.report_date,
             timing: payload.timing,
             status: 'pending',
             started_at: new Date().toISOString(),
           }),
         }
       );
 
       if (!insertResponse.ok) {
         // Check if it's a duplicate key error (already exists)
         const errorText = await insertResponse.text();
         if (!errorText.includes('duplicate key')) {
           console.error(`Failed to create processing run for ${payload.ticker}: ${errorText}`);
         }
       }
     }
 
     // Determine Modal endpoint
     const endpoint = modal_endpoint || Deno.env.get('MODAL_WEBHOOK_URL');
     
     if (!endpoint) {
       // If no endpoint configured, just log and return success
       console.log('No Modal endpoint configured, skipping Modal trigger');
       return new Response(
         JSON.stringify({
           success: true,
           message: 'Processing runs created, but no Modal endpoint configured',
           tickers: tickerPayloads.map(t => t.ticker),
           tickers_count: tickerPayloads.length,
         }),
         { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
       );
     }
 
     // Call Modal webhook
     console.log(`Triggering Modal endpoint: ${endpoint}`);
     
     const modalResponse = await fetch(endpoint, {
       method: 'POST',
       headers: {
         'Content-Type': 'application/json',
         'Authorization': `Bearer ${modalWebhookSecret}`,
       },
       body: JSON.stringify({
         tickers: tickerPayloads,
         supabase_url: Deno.env.get('EXTERNAL_SUPABASE_URL'),
         callback_url: `${supabaseUrl}/functions/v1/excel-agent-callback`,
       }),
     });
 
     if (!modalResponse.ok) {
       const errorText = await modalResponse.text();
       console.error(`Modal webhook failed: ${errorText}`);
       
       // Update processing runs to failed status
       for (const payload of tickerPayloads) {
         await fetch(
           `${supabaseUrl}/rest/v1/excel_processing_runs?ticker=eq.${payload.ticker}&report_date=eq.${payload.report_date}&timing=eq.${payload.timing}`,
           {
             method: 'PATCH',
             headers: {
               'apikey': supabaseKey,
               'Authorization': `Bearer ${supabaseKey}`,
               'Content-Type': 'application/json',
             },
             body: JSON.stringify({
               status: 'failed',
               error_message: `Modal webhook failed: ${errorText}`,
               completed_at: new Date().toISOString(),
             }),
           }
         );
       }
 
       return new Response(
         JSON.stringify({ success: false, error: `Modal webhook failed: ${errorText}` }),
         { status: 502, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
       );
     }
 
     const modalResult = await modalResponse.json();
     console.log('Modal webhook triggered successfully:', modalResult);
 
     return new Response(
       JSON.stringify({
         success: true,
         message: `Triggered processing for ${tickerPayloads.length} tickers`,
         tickers: tickerPayloads.map(t => t.ticker),
         tickers_count: tickerPayloads.length,
         modal_response: modalResult,
       }),
       { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
     );
 
   } catch (error) {
     console.error('Error in trigger-excel-agent:', error);
     const errorMessage = error instanceof Error ? error.message : 'Unknown error';
     return new Response(
       JSON.stringify({ success: false, error: errorMessage }),
       { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
     );
   }
 });