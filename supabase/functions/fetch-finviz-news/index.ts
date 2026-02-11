import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

/** Lightweight CSV parser that handles quoted fields with commas */
function parseCSV(text: string): Record<string, string>[] {
  const lines = text.trim().split("\n");
  if (lines.length < 2) return [];

  const headers = parseCSVLine(lines[0]);
  const rows: Record<string, string>[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    if (values.length === 0) continue;
    const row: Record<string, string> = {};
    for (let j = 0; j < headers.length; j++) {
      row[headers[j]] = values[j] ?? "";
    }
    rows.push(row);
  }
  return rows;
}

function parseCSVLine(line: string): string[] {
  const fields: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (i + 1 < line.length && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        current += ch;
      }
    } else {
      if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        fields.push(current.trim());
        current = "";
      } else {
        current += ch;
      }
    }
  }
  fields.push(current.trim());
  return fields;
}

interface EndpointConfig {
  param: string;
  table: string;
  hasTicker: boolean;
}

const ENDPOINTS: EndpointConfig[] = [
  { param: "c=1", table: "rolling_market_news", hasTicker: false },
  { param: "v=3", table: "rolling_stock_news", hasTicker: true },
  { param: "v=4", table: "rolling_etf_news", hasTicker: true },
  { param: "v=5", table: "rolling_crypto_news", hasTicker: true },
];

const MAX_ROWS = 300;
const SUMMARY_BATCH_SIZE = 3;
const SUMMARY_LIMIT = 25;

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const authToken = Deno.env.get("FINVIZ_AUTH_TOKEN");
    if (!authToken) {
      throw new Error("FINVIZ_AUTH_TOKEN not configured");
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    const results: Record<string, { fetched: number; upserted: number; error?: string }> = {};

    for (const endpoint of ENDPOINTS) {
      try {
        const url = `https://elite.finviz.com/news_export.ashx?${endpoint.param}&auth=${authToken}`;
        console.log(`Fetching ${endpoint.table} from ${url.replace(authToken, '***')}`);

        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const csvText = await response.text();
        const rows = parseCSV(csvText);
        console.log(`Parsed ${rows.length} rows for ${endpoint.table}`);

        if (rows.length === 0) {
          results[endpoint.table] = { fetched: 0, upserted: 0 };
          continue;
        }

        // Build upsert data
        const upsertData = rows.map((row) => {
          const base: Record<string, unknown> = {
            title: row["Title"] || "",
            source: row["Source"] || "",
            published_at: row["Date"] || new Date().toISOString(),
            url: row["Url"] || "",
            category: row["Category"] || "",
          };
          if (endpoint.hasTicker) {
            base.ticker = row["Ticker"] || null;
          }
          return base;
        }).filter((r) => r.url !== "");

        // Upsert in batches of 50
        let upserted = 0;
        for (let i = 0; i < upsertData.length; i += 50) {
          const batch = upsertData.slice(i, i + 50);
          const { error } = await supabase
            .from(endpoint.table)
            .upsert(batch, { onConflict: "url", ignoreDuplicates: false });

          if (error) {
            console.error(`Upsert error for ${endpoint.table}:`, error);
            throw error;
          }
          upserted += batch.length;
        }

        // Trim to MAX_ROWS: find the cutoff published_at
        const { data: cutoffRow } = await supabase
          .from(endpoint.table)
          .select("published_at")
          .order("published_at", { ascending: false })
          .range(MAX_ROWS - 1, MAX_ROWS - 1)
          .single();

        if (cutoffRow) {
          const { error: deleteError } = await supabase
            .from(endpoint.table)
            .delete()
            .lt("published_at", cutoffRow.published_at);

          if (deleteError) {
            console.error(`Trim error for ${endpoint.table}:`, deleteError);
          }
        }

        results[endpoint.table] = { fetched: rows.length, upserted };
      } catch (err) {
        console.error(`Error processing ${endpoint.table}:`, err);
        results[endpoint.table] = {
          fetched: 0,
          upserted: 0,
          error: err.message,
        };
      }
    }

    console.log("Fetch results:", JSON.stringify(results));

    // === Phase 2: Summarize unsummarized articles via Firecrawl v2 ===
    const firecrawlKey = Deno.env.get("FIRECRAWL_API_KEY");
    const summaryResults: Record<string, { attempted: number; succeeded: number; errors: number }> = {};

    if (firecrawlKey) {
      for (const endpoint of ENDPOINTS) {
        const stats = { attempted: 0, succeeded: 0, errors: 0 };
        try {
          const { data: unsummarized, error: queryError } = await supabase
            .from(endpoint.table)
            .select("id, url")
            .is("summary", null)
            .order("published_at", { ascending: false })
            .limit(SUMMARY_LIMIT);

          if (queryError || !unsummarized || unsummarized.length === 0) {
            if (queryError) console.error(`Summary query error for ${endpoint.table}:`, queryError);
            summaryResults[endpoint.table] = stats;
            continue;
          }

          stats.attempted = unsummarized.length;
          console.log(`Summarizing ${unsummarized.length} articles for ${endpoint.table}`);

          // Process in chunks of SUMMARY_BATCH_SIZE
          for (let i = 0; i < unsummarized.length; i += SUMMARY_BATCH_SIZE) {
            const chunk = unsummarized.slice(i, i + SUMMARY_BATCH_SIZE);
            const promises = chunk.map(async (article) => {
              try {
                const res = await fetch("https://api.firecrawl.dev/v2/scrape", {
                  method: "POST",
                  headers: {
                    Authorization: `Bearer ${firecrawlKey}`,
                    "Content-Type": "application/json",
                  },
                  body: JSON.stringify({
                    url: article.url,
                    onlyMainContent: true,
                    maxAge: 172800000,
                    formats: ["summary"],
                  }),
                });

                if (!res.ok) {
                  console.error(`Firecrawl error for ${article.url}: HTTP ${res.status}`);
                  stats.errors++;
                  return;
                }

                const json = await res.json();
                const summary = json?.data?.summary || json?.summary || null;

                if (summary) {
                  const { error: updateError } = await supabase
                    .from(endpoint.table)
                    .update({ summary })
                    .eq("id", article.id);

                  if (updateError) {
                    console.error(`Update error for ${article.id}:`, updateError);
                    stats.errors++;
                  } else {
                    stats.succeeded++;
                  }
                } else {
                  console.warn(`No summary returned for ${article.url}`);
                  stats.errors++;
                }
              } catch (e) {
                console.error(`Scrape failed for ${article.url}:`, e);
                stats.errors++;
              }
            });

            await Promise.all(promises);
          }
        } catch (e) {
          console.error(`Summary phase error for ${endpoint.table}:`, e);
        }
        summaryResults[endpoint.table] = stats;
      }
    } else {
      console.warn("FIRECRAWL_API_KEY not set, skipping summary phase");
    }

    console.log("Summary results:", JSON.stringify(summaryResults));

    return new Response(JSON.stringify({ success: true, results, summaryResults }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("Fatal error:", err);
    return new Response(
      JSON.stringify({ success: false, error: err.message }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
