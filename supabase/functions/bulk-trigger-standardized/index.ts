const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { tickers } = await req.json();

    if (!Array.isArray(tickers) || tickers.length === 0) {
      return new Response(
        JSON.stringify({ success: false, error: 'tickers array is required' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Validate each ticker object
    for (const t of tickers) {
      if (!t.ticker || !t.report_date || !t.timing) {
        return new Response(
          JSON.stringify({ success: false, error: `Each ticker must have ticker, report_date, and timing. Invalid: ${JSON.stringify(t)}` }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }
    }

    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const modalWebhookSecret = Deno.env.get('MODAL_WEBHOOK_SECRET');
    const modalEndpoint = Deno.env.get('MODAL_WEBHOOK_URL');

    if (!modalWebhookSecret || !modalEndpoint) {
      return new Response(
        JSON.stringify({ success: false, error: 'MODAL_WEBHOOK_SECRET or MODAL_WEBHOOK_URL not configured' }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Batch insert all processing run records
    const records = tickers.map((t: any) => ({
      ticker: t.ticker.toUpperCase().trim(),
      status: 'pending',
      started_at: new Date().toISOString(),
      report_date: t.report_date,
      timing: t.timing,
      fiscal_period_end: t.fiscal_period_end || null,
    }));

    // Insert in chunks of 50 to avoid payload limits
    const CHUNK_SIZE = 50;
    for (let i = 0; i < records.length; i += CHUNK_SIZE) {
      const chunk = records.slice(i, i + CHUNK_SIZE);
      const insertResponse = await fetch(
        `${supabaseUrl}/rest/v1/standardized_processing_runs`,
        {
          method: 'POST',
          headers: {
            'apikey': supabaseKey,
            'Authorization': `Bearer ${supabaseKey}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal',
          },
          body: JSON.stringify(chunk),
        }
      );

      if (!insertResponse.ok) {
        const errorText = await insertResponse.text();
        console.error(`Failed to insert batch ${i / CHUNK_SIZE + 1}: ${errorText}`);
      }
    }

    // Call Modal webhook with all tickers in one request
    // Modal's .spawn() handles concurrency per ticker
    const modalPayload = {
      tickers: records.map((r: any) => ({
        ticker: r.ticker,
        report_date: r.report_date,
        timing: r.timing,
        fiscal_period_end: r.fiscal_period_end,
      })),
      callback_url: `${supabaseUrl}/functions/v1/standardized-agent-callback`,
    };

    console.log(`Triggering Modal for ${records.length} tickers`);

    const modalResponse = await fetch(modalEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${modalWebhookSecret}`,
      },
      body: JSON.stringify(modalPayload),
    });

    if (!modalResponse.ok) {
      const errorText = await modalResponse.text();
      console.error(`Modal webhook failed: ${errorText}`);
      return new Response(
        JSON.stringify({
          success: false,
          error: `Modal webhook failed: ${errorText}`,
          records_created: records.length,
        }),
        { status: 502, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const modalResult = await modalResponse.json();
    console.log('Modal bulk trigger success:', modalResult);

    return new Response(
      JSON.stringify({
        success: true,
        message: `Queued ${records.length} tickers for standardized processing`,
        count: records.length,
        modal_response: modalResult,
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error('Error in bulk-trigger-standardized:', error);
    return new Response(
      JSON.stringify({ success: false, error: error instanceof Error ? error.message : 'Unknown error' }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
