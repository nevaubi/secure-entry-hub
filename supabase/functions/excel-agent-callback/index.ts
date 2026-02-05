 const corsHeaders = {
   'Access-Control-Allow-Origin': '*',
   'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
 };
 
 interface CallbackPayload {
   ticker: string;
   report_date: string;
   timing: 'premarket' | 'afterhours';
   status: 'completed' | 'failed';
   files_updated?: number;
   data_sources_used?: string[];
   error_message?: string;
 }
 
 Deno.serve(async (req) => {
   if (req.method === 'OPTIONS') {
     return new Response(null, { headers: corsHeaders });
   }
 
   try {
     // Verify webhook secret
     const authHeader = req.headers.get('Authorization');
     const modalWebhookSecret = Deno.env.get('MODAL_WEBHOOK_SECRET');
 
     if (!authHeader || authHeader !== `Bearer ${modalWebhookSecret}`) {
       return new Response(
         JSON.stringify({ success: false, error: 'Unauthorized' }),
         { status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
       );
     }
 
     const payload: CallbackPayload = await req.json();
     console.log('Received callback for:', payload.ticker, payload.status);
 
     const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
     const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
 
     // Update the processing run record
     const updateData: Record<string, unknown> = {
       status: payload.status,
       completed_at: new Date().toISOString(),
     };
 
     if (payload.files_updated !== undefined) {
       updateData.files_updated = payload.files_updated;
     }
 
     if (payload.data_sources_used) {
       updateData.data_sources_used = payload.data_sources_used;
     }
 
     if (payload.error_message) {
       updateData.error_message = payload.error_message;
     }
 
     const updateResponse = await fetch(
       `${supabaseUrl}/rest/v1/excel_processing_runs?ticker=eq.${payload.ticker}&report_date=eq.${payload.report_date}&timing=eq.${payload.timing}`,
       {
         method: 'PATCH',
         headers: {
           'apikey': supabaseKey,
           'Authorization': `Bearer ${supabaseKey}`,
           'Content-Type': 'application/json',
         },
         body: JSON.stringify(updateData),
       }
     );
 
     if (!updateResponse.ok) {
       const errorText = await updateResponse.text();
       console.error('Failed to update processing run:', errorText);
       return new Response(
         JSON.stringify({ success: false, error: `Failed to update: ${errorText}` }),
         { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
       );
     }
 
     console.log(`Successfully updated processing run for ${payload.ticker}`);
 
     return new Response(
       JSON.stringify({ success: true, message: 'Callback processed' }),
       { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
     );
 
   } catch (error) {
     console.error('Error in excel-agent-callback:', error);
     const errorMessage = error instanceof Error ? error.message : 'Unknown error';
     return new Response(
       JSON.stringify({ success: false, error: errorMessage }),
       { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
     );
   }
 });