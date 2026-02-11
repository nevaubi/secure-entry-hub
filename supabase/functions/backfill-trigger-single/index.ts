const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { ticker, report_date, fiscal_period_end, timing } = await req.json();

    if (!ticker || !report_date || !timing) {
      return new Response(
        JSON.stringify({ success: false, error: 'Missing required fields: ticker, report_date, timing' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const modalWebhookSecret = Deno.env.get('MODAL_WEBHOOK_SECRET');
    const modalEndpoint = Deno.env.get('MODAL_WEBHOOK_URL');

    if (!modalWebhookSecret || !modalEndpoint) {
      return new Response(
        JSON.stringify({ success: false, error: 'Modal webhook not configured' }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Create processing run record (skip if exists)
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
          ticker,
          report_date,
          timing,
          status: 'pending',
          started_at: new Date().toISOString(),
        }),
      }
    );

    if (!insertResponse.ok) {
      const errorText = await insertResponse.text();
      if (!errorText.includes('duplicate key')) {
        console.error(`Failed to create processing run for ${ticker}: ${errorText}`);
      } else {
        // Update existing record back to pending
        await fetch(
          `${supabaseUrl}/rest/v1/excel_processing_runs?ticker=eq.${ticker}&report_date=eq.${report_date}&timing=eq.${timing}`,
          {
            method: 'PATCH',
            headers: {
              'apikey': supabaseKey,
              'Authorization': `Bearer ${supabaseKey}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              status: 'pending',
              started_at: new Date().toISOString(),
              error_message: null,
              completed_at: null,
            }),
          }
        );
      }
    }

    // Call Modal webhook with single ticker
    console.log(`Triggering Modal for ${ticker} (${report_date})`);

    const modalResponse = await fetch(modalEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${modalWebhookSecret}`,
      },
      body: JSON.stringify({
        tickers: [{
          ticker,
          report_date,
          fiscal_period_end: fiscal_period_end || null,
          timing,
        }],
        supabase_url: Deno.env.get('EXTERNAL_SUPABASE_URL'),
        callback_url: `${Deno.env.get('SUPABASE_URL')}/functions/v1/excel-agent-callback`,
      }),
    });

    if (!modalResponse.ok) {
      const errorText = await modalResponse.text();
      console.error(`Modal webhook failed: ${errorText}`);

      // Update processing run to failed
      await fetch(
        `${supabaseUrl}/rest/v1/excel_processing_runs?ticker=eq.${ticker}&report_date=eq.${report_date}&timing=eq.${timing}`,
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

      return new Response(
        JSON.stringify({ success: false, error: `Modal webhook failed: ${errorText}` }),
        { status: 502, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const modalResult = await modalResponse.json();

    return new Response(
      JSON.stringify({
        success: true,
        message: `Triggered processing for ${ticker}`,
        ticker,
        report_date,
        modal_response: modalResult,
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error('Error in backfill-trigger-single:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return new Response(
      JSON.stringify({ success: false, error: errorMessage }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
