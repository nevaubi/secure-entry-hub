import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const BATCH_SIZE = 50;

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // Local client
    const localClient = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // External client
    const externalClient = createClient(
      Deno.env.get("EXTERNAL_SUPABASE_URL")!,
      Deno.env.get("EXTERNAL_SUPABASE_SERVICE_KEY")!
    );

    // Fetch local rows with non-null summary
    const { data: rows, error: fetchError } = await localClient
      .from("rolling_market_news")
      .select("title, source, published_at, url, category, summary")
      .not("summary", "is", null)
      .limit(300);

    if (fetchError) {
      throw new Error(`Failed to fetch local news: ${fetchError.message}`);
    }

    if (!rows || rows.length === 0) {
      return new Response(
        JSON.stringify({ synced: 0, errors: [], message: "No rows to sync" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    console.log(`Fetched ${rows.length} rows to sync`);

    const errors: string[] = [];
    let synced = 0;

    // Upsert in batches
    for (let i = 0; i < rows.length; i += BATCH_SIZE) {
      const batch = rows.slice(i, i + BATCH_SIZE);

      const { error: upsertError } = await externalClient
        .from("rolling_market_news")
        .upsert(batch, { onConflict: "url" });

      if (upsertError) {
        const msg = `Batch ${Math.floor(i / BATCH_SIZE) + 1} error: ${upsertError.message}`;
        console.error(msg);
        errors.push(msg);
      } else {
        synced += batch.length;
      }
    }

    const result = { synced, errors, total_fetched: rows.length };
    console.log("Sync complete:", JSON.stringify(result));

    return new Response(JSON.stringify(result), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("Sync failed:", err.message);
    return new Response(
      JSON.stringify({ error: err.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
