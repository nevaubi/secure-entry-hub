import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const BATCH_SIZE = 50;

// Tables to sync
const TABLES_CONFIG = [
  "rolling_market_news",
  "rolling_stock_news",
  "rolling_etf_news",
  "rolling_crypto_news",
];

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

    const allErrors: string[] = [];
    let totalSynced = 0;
    const resultsByTable: Record<string, { synced: number; errors: string[] }> = {};

    // Process each table
    for (const tableName of TABLES_CONFIG) {
      console.log(`Processing table: ${tableName}`);

      // Fetch local rows with non-null summary
      const { data: rows, error: fetchError } = await localClient
        .from(tableName)
        .select(
          tableName === "rolling_market_news"
            ? "title, source, published_at, url, category, summary"
            : "title, source, published_at, url, category, summary, ticker"
        )
        .not("summary", "is", null)
        .limit(300);

      if (fetchError) {
        const msg = `Failed to fetch ${tableName}: ${fetchError.message}`;
        console.error(msg);
        allErrors.push(msg);
        resultsByTable[tableName] = { synced: 0, errors: [msg] };
        continue;
      }

      if (!rows || rows.length === 0) {
        console.log(`No rows to sync for ${tableName}`);
        resultsByTable[tableName] = { synced: 0, errors: [] };
        continue;
      }

      console.log(`Fetched ${rows.length} rows from ${tableName}`);

      const tableErrors: string[] = [];
      let tableSynced = 0;

      // Upsert in batches
      for (let i = 0; i < rows.length; i += BATCH_SIZE) {
        const batch = rows.slice(i, i + BATCH_SIZE);

        const { error: upsertError } = await externalClient
          .from(tableName)
          .upsert(batch, { onConflict: "url" });

        if (upsertError) {
          const msg = `${tableName} batch ${Math.floor(i / BATCH_SIZE) + 1} error: ${upsertError.message}`;
          console.error(msg);
          tableErrors.push(msg);
        } else {
          tableSynced += batch.length;
        }
      }

      totalSynced += tableSynced;
      resultsByTable[tableName] = { synced: tableSynced, errors: tableErrors };
      allErrors.push(...tableErrors);

      console.log(`Synced ${tableSynced} rows to ${tableName}`);
    }

    const result = { totalSynced, resultsByTable, allErrors };
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
