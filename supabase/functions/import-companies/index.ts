 import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
 import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
 
 const corsHeaders = {
   "Access-Control-Allow-Origin": "*",
   "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
 };
 
 interface CompanyRow {
   company_id: number;
   ticker: string;
   name: string;
   cik: number | null;
   exchange: string | null;
   sector: string | null;
   description: string | null;
   year_founded: number | null;
   logo_url: string | null;
 }
 
 serve(async (req) => {
   if (req.method === "OPTIONS") {
     return new Response(null, { headers: corsHeaders });
   }
 
   try {
     const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
     const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
     
     const supabase = createClient(supabaseUrl, supabaseServiceKey);
 
     const { companies } = await req.json() as { companies: CompanyRow[] };
 
     if (!companies || !Array.isArray(companies)) {
       return new Response(
         JSON.stringify({ error: "Invalid request: companies array required" }),
         { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
       );
     }
 
     console.log(`Importing ${companies.length} companies...`);
 
     // Insert in batches of 100
     const batchSize = 100;
     let totalInserted = 0;
 
     for (let i = 0; i < companies.length; i += batchSize) {
       const batch = companies.slice(i, i + batchSize);
       
       const { error } = await supabase
         .from("companies")
         .upsert(batch, { onConflict: "ticker" });
 
       if (error) {
         console.error(`Error inserting batch starting at ${i}:`, error);
         return new Response(
           JSON.stringify({ error: `Failed at batch ${i}: ${error.message}` }),
           { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
         );
       }
 
       totalInserted += batch.length;
       console.log(`Inserted ${totalInserted}/${companies.length} companies`);
     }
 
     return new Response(
       JSON.stringify({ success: true, count: totalInserted }),
       { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
     );
   } catch (error) {
     console.error("Error:", error);
     const errorMessage = error instanceof Error ? error.message : String(error);
     return new Response(
       JSON.stringify({ error: errorMessage }),
       { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
     );
   }
 });