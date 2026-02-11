import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const TABLES = [
  "rolling_market_news",
  "rolling_stock_news",
  "rolling_etf_news",
  "rolling_crypto_news",
];

const BATCH_SIZE = 3; // concurrent Firecrawl calls
const PER_TABLE_LIMIT = 15; // max unsummarized rows per table per run
const PER_URL_TIMEOUT_MS = 30_000; // 30s timeout per scrape

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const firecrawlKey = Deno.env.get("FIRECRAWL_API_KEY");
    if (!firecrawlKey) {
      throw new Error("FIRECRAWL_API_KEY not configured");
    }

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const summaryResults: Record<
      string,
      { attempted: number; succeeded: number; errors: number }
    > = {};

    for (const tableName of TABLES) {
      const stats = { attempted: 0, succeeded: 0, errors: 0 };

      try {
        const { data: unsummarized, error: queryError } = await supabase
          .from(tableName)
          .select("id, url")
          .is("summary", null)
          .order("published_at", { ascending: false })
          .limit(PER_TABLE_LIMIT);

        if (queryError) {
          console.error(`Query error for ${tableName}:`, queryError.message);
          summaryResults[tableName] = stats;
          continue;
        }

        if (!unsummarized || unsummarized.length === 0) {
          console.log(`No unsummarized rows for ${tableName}`);
          summaryResults[tableName] = stats;
          continue;
        }

        stats.attempted = unsummarized.length;
        console.log(
          `Summarizing ${unsummarized.length} articles for ${tableName}`
        );

        // Process in small concurrent batches
        for (let i = 0; i < unsummarized.length; i += BATCH_SIZE) {
          const chunk = unsummarized.slice(i, i + BATCH_SIZE);

          const promises = chunk.map(async (article) => {
            const controller = new AbortController();
            const timeout = setTimeout(
              () => controller.abort(),
              PER_URL_TIMEOUT_MS
            );

            try {
              const res = await fetch(
                "https://api.firecrawl.dev/v2/scrape",
                {
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
                  signal: controller.signal,
                }
              );

              if (!res.ok) {
                console.error(
                  `Firecrawl error for ${article.url}: HTTP ${res.status}`
                );
                stats.errors++;
                return;
              }

              const json = await res.json();
              const summary =
                json?.data?.summary || json?.summary || null;

              if (summary) {
                const { error: updateError } = await supabase
                  .from(tableName)
                  .update({ summary })
                  .eq("id", article.id);

                if (updateError) {
                  console.error(
                    `Update error for ${article.id}:`,
                    updateError.message
                  );
                  stats.errors++;
                } else {
                  stats.succeeded++;
                }
              } else {
                console.warn(`No summary returned for ${article.url}`);
                stats.errors++;
              }
            } catch (e) {
              if (e.name === "AbortError") {
                console.error(`Timeout scraping ${article.url}`);
              } else {
                console.error(`Scrape failed for ${article.url}:`, e.message);
              }
              stats.errors++;
            } finally {
              clearTimeout(timeout);
            }
          });

          await Promise.all(promises);
        }
      } catch (e) {
        console.error(`Error processing ${tableName}:`, e.message);
      }

      summaryResults[tableName] = stats;
      console.log(
        `${tableName}: ${stats.succeeded}/${stats.attempted} summarized, ${stats.errors} errors`
      );
    }

    console.log("Summary run complete:", JSON.stringify(summaryResults));

    return new Response(JSON.stringify({ success: true, summaryResults }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("Fatal error:", err.message);
    return new Response(JSON.stringify({ success: false, error: err.message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
