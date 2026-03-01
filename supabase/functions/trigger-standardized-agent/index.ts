const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { ticker, report_date, timing, fiscal_period_end, modal_endpoint } = await req.json();

    if (!ticker || typeof ticker !== 'string') {
      return new Response(
        JSON.stringify({ success: false, error: 'ticker is required' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    if (!report_date || typeof report_date !== 'string') {
      return new Response(
        JSON.stringify({ success: false, error: 'report_date is required' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    if (!timing || (timing !== 'premarket' && timing !== 'afterhours')) {
      return new Response(
        JSON.stringify({ success: false, error: 'timing must be "premarket" or "afterhours"' }),
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

    const upperTicker = ticker.toUpperCase();
    console.log(`Triggering standardized agent for ticker: ${upperTicker}, report_date: ${report_date}, timing: ${timing}`);

    // Create processing run record
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
        body: JSON.stringify({
          ticker: upperTicker,
          status: 'pending',
          started_at: new Date().toISOString(),
          report_date,
          timing,
          fiscal_period_end: fiscal_period_end || null,
        }),
      }
    );

    if (!insertResponse.ok) {
      const errorText = await insertResponse.text();
      if (!errorText.includes('duplicate key')) {
        console.error(`Failed to create processing run: ${errorText}`);
      }
    }

    // Determine Modal endpoint
    const endpoint = modal_endpoint || Deno.env.get('MODAL_WEBHOOK_URL');

    if (!endpoint) {
      return new Response(
        JSON.stringify({
          success: true,
          message: 'Processing run created, but no Modal endpoint configured',
          ticker: upperTicker,
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
        tickers: [{
          ticker: upperTicker,
          report_date,
          timing,
          fiscal_period_end: fiscal_period_end || null,
        }],
        callback_url: `${supabaseUrl}/functions/v1/standardized-agent-callback`,
      }),
    });

    if (!modalResponse.ok) {
      const errorText = await modalResponse.text();
      console.error(`Modal webhook failed: ${errorText}`);

      // Update processing run to failed
      await fetch(
        `${supabaseUrl}/rest/v1/standardized_processing_runs?ticker=eq.${upperTicker}&status=eq.pending`,
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
    console.log('Modal webhook triggered successfully:', modalResult);

    return new Response(
      JSON.stringify({
        success: true,
        message: `Triggered standardized processing for ${upperTicker}`,
        ticker: upperTicker,
        modal_response: modalResult,
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error('Error in trigger-standardized-agent:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return new Response(
      JSON.stringify({ success: false, error: errorMessage }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
