import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const FIRECRAWL_API_KEY = Deno.env.get("FIRECRAWL_API_KEY");
    if (!FIRECRAWL_API_KEY) {
      throw new Error("FIRECRAWL_API_KEY is not configured");
    }

    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) {
      throw new Error("LOVABLE_API_KEY is not configured");
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Step 1: Use Firecrawl to screenshot Yahoo Finance futures page
    console.log("Step 1: Calling Firecrawl to screenshot Yahoo Finance...");
    const firecrawlResponse = await fetch("https://api.firecrawl.dev/v1/scrape", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${FIRECRAWL_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url: "https://finance.yahoo.com/markets/commodities/",
        actions: [
          { type: "wait", milliseconds: 3000 },
          { type: "screenshot", fullPage: false },
        ],
        formats: ["screenshot"],
      }),
    });

    const firecrawlData = await firecrawlResponse.json();

    if (!firecrawlResponse.ok) {
      console.error("Firecrawl API error:", JSON.stringify(firecrawlData));
      throw new Error(`Firecrawl failed [${firecrawlResponse.status}]: ${JSON.stringify(firecrawlData)}`);
    }

    const screenshotUrl = firecrawlData?.data?.screenshot || firecrawlData?.screenshot;
    if (!screenshotUrl) {
      console.error("No screenshot returned from Firecrawl:", JSON.stringify(firecrawlData));
      throw new Error("No screenshot URL returned from Firecrawl");
    }

    console.log("Screenshot captured successfully:", screenshotUrl.substring(0, 100) + "...");

    // Helper to generate 8 fields per instrument
    const makeFields = (prefix: string, symbol: string, desc: string) => ({
      [`${prefix}_symbol`]: { type: "string", description: `${desc} symbol, e.g. '${symbol}'` },
      [`${prefix}_name`]: { type: "string", description: `${desc} contract name` },
      [`${prefix}_price`]: { type: "number", description: `${desc} futures price` },
      [`${prefix}_market_time`]: { type: "string", description: `${desc} market time, e.g. '11:37AM EST'` },
      [`${prefix}_change`]: { type: "number", description: `${desc} nominal change (positive or negative)` },
      [`${prefix}_change_pct`]: { type: "number", description: `${desc} percent change (positive or negative)` },
      [`${prefix}_volume`]: { type: "string", description: `${desc} volume as displayed` },
      [`${prefix}_open_interest`]: { type: "string", description: `${desc} open interest as displayed` },
    });

    const allProperties = {
      ...makeFields("dow", "YM=F", "Dow"),
      ...makeFields("sp500", "ES=F", "S&P 500"),
      ...makeFields("nas", "NQ=F", "Nasdaq 100"),
      ...makeFields("gold", "GC=F", "Gold"),
      ...makeFields("silver", "SI=F", "Silver"),
      ...makeFields("crude", "CL=F", "Crude Oil"),
      ...makeFields("tnote10", "ZN=F", "10-Year T-Note"),
      ...makeFields("tnote5", "ZF=F", "5-Year T-Note"),
      ...makeFields("tnote2", "ZT=F", "2-Year T-Note"),
    };

    const allRequired = Object.keys(allProperties);

    // Step 2: Send screenshot to Gemini for structured extraction
    console.log("Step 2: Sending screenshot to Gemini for extraction of 9 instruments...");
    const geminiResponse = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-3-flash-preview",
        messages: [
          {
            role: "system",
            content:
              "You are a precise data extraction assistant. You will be given a screenshot of Yahoo Finance's futures/commodities page showing a table of futures contracts. Extract data for exactly 9 futures: YM=F (Mini Dow Jones), ES=F (E-Mini S&P 500), NQ=F (Nasdaq 100), GC=F (Gold), SI=F (Silver), CL=F (Crude Oil), ZN=F (10-Year T-Note), ZF=F (5-Year T-Note), ZT=F (2-Year T-Note). The table has columns: Symbol, Name, Price, Market Time, Change, Change %, Volume, Open Interest. Be extremely precise with the numbers. Store volume and open interest as text exactly as displayed (e.g. '1.061M', '95,915').",
          },
          {
            role: "user",
            content: [
              {
                type: "text",
                text: "Extract futures data from this Yahoo Finance screenshot. Find the rows for these 9 symbols: YM=F (Dow), ES=F (S&P 500), NQ=F (Nasdaq 100), GC=F (Gold), SI=F (Silver), CL=F (Crude Oil), ZN=F (10-Year T-Note), ZF=F (5-Year T-Note), ZT=F (2-Year T-Note). For each, extract: symbol, name, price, market time, change, change %, volume, and open interest.",
              },
              {
                type: "image_url",
                image_url: { url: screenshotUrl },
              },
            ],
          },
        ],
        tools: [
          {
            type: "function",
            function: {
              name: "extract_premarket_futures",
              description: "Extract futures data from Yahoo Finance screenshot for 9 instruments: Dow, S&P 500, Nasdaq 100, Gold, Silver, Crude Oil, 10Y T-Note, 5Y T-Note, 2Y T-Note",
              parameters: {
                type: "object",
                properties: allProperties,
                required: allRequired,
                additionalProperties: false,
              },
            },
          },
        ],
        tool_choice: { type: "function", function: { name: "extract_premarket_futures" } },
      }),
    });

    if (!geminiResponse.ok) {
      const errorText = await geminiResponse.text();
      console.error("Gemini API error:", geminiResponse.status, errorText);
      throw new Error(`Gemini failed [${geminiResponse.status}]: ${errorText}`);
    }

    const geminiData = await geminiResponse.json();
    console.log("Gemini raw response:", JSON.stringify(geminiData).substring(0, 500));

    // Parse tool call response
    const toolCall = geminiData?.choices?.[0]?.message?.tool_calls?.[0];
    if (!toolCall?.function?.arguments) {
      console.error("No tool call in Gemini response:", JSON.stringify(geminiData));
      throw new Error("Gemini did not return structured tool call data");
    }

    const extracted = typeof toolCall.function.arguments === "string"
      ? JSON.parse(toolCall.function.arguments)
      : toolCall.function.arguments;

    console.log("Extracted data:", JSON.stringify(extracted));

    // Step 3: Delete all existing rows, then insert fresh data
    console.log("Step 3: Deleting old rows and inserting fresh data...");
    const { error: deleteError } = await supabase
      .from("recurring_premarket_data")
      .delete()
      .neq("id", "00000000-0000-0000-0000-000000000000");

    if (deleteError) {
      console.error("Database delete error:", deleteError);
      throw new Error(`DB delete failed: ${deleteError.message}`);
    }

    const { data: insertData, error: insertError } = await supabase
      .from("recurring_premarket_data")
      .insert({
        captured_at: new Date().toISOString(),
        // Dow
        dow_symbol: extracted.dow_symbol,
        dow_name: extracted.dow_name,
        dow_price: extracted.dow_price,
        dow_market_time: extracted.dow_market_time,
        dow_change: extracted.dow_change,
        dow_change_pct: extracted.dow_change_pct,
        dow_volume: extracted.dow_volume,
        dow_open_interest: extracted.dow_open_interest,
        // S&P 500
        sp500_symbol: extracted.sp500_symbol,
        sp500_name: extracted.sp500_name,
        sp500_price: extracted.sp500_price,
        sp500_market_time: extracted.sp500_market_time,
        sp500_change: extracted.sp500_change,
        sp500_change_pct: extracted.sp500_change_pct,
        sp500_volume: extracted.sp500_volume,
        sp500_open_interest: extracted.sp500_open_interest,
        // Nasdaq
        nas_symbol: extracted.nas_symbol,
        nas_name: extracted.nas_name,
        nas_price: extracted.nas_price,
        nas_market_time: extracted.nas_market_time,
        nas_change: extracted.nas_change,
        nas_change_pct: extracted.nas_change_pct,
        nas_volume: extracted.nas_volume,
        nas_open_interest: extracted.nas_open_interest,
        // Gold
        gold_symbol: extracted.gold_symbol,
        gold_name: extracted.gold_name,
        gold_price: extracted.gold_price,
        gold_market_time: extracted.gold_market_time,
        gold_change: extracted.gold_change,
        gold_change_pct: extracted.gold_change_pct,
        gold_volume: extracted.gold_volume,
        gold_open_interest: extracted.gold_open_interest,
        // Silver
        silver_symbol: extracted.silver_symbol,
        silver_name: extracted.silver_name,
        silver_price: extracted.silver_price,
        silver_market_time: extracted.silver_market_time,
        silver_change: extracted.silver_change,
        silver_change_pct: extracted.silver_change_pct,
        silver_volume: extracted.silver_volume,
        silver_open_interest: extracted.silver_open_interest,
        // Crude Oil
        crude_symbol: extracted.crude_symbol,
        crude_name: extracted.crude_name,
        crude_price: extracted.crude_price,
        crude_market_time: extracted.crude_market_time,
        crude_change: extracted.crude_change,
        crude_change_pct: extracted.crude_change_pct,
        crude_volume: extracted.crude_volume,
        crude_open_interest: extracted.crude_open_interest,
        // 10-Year T-Note
        tnote10_symbol: extracted.tnote10_symbol,
        tnote10_name: extracted.tnote10_name,
        tnote10_price: extracted.tnote10_price,
        tnote10_market_time: extracted.tnote10_market_time,
        tnote10_change: extracted.tnote10_change,
        tnote10_change_pct: extracted.tnote10_change_pct,
        tnote10_volume: extracted.tnote10_volume,
        tnote10_open_interest: extracted.tnote10_open_interest,
        // 5-Year T-Note
        tnote5_symbol: extracted.tnote5_symbol,
        tnote5_name: extracted.tnote5_name,
        tnote5_price: extracted.tnote5_price,
        tnote5_market_time: extracted.tnote5_market_time,
        tnote5_change: extracted.tnote5_change,
        tnote5_change_pct: extracted.tnote5_change_pct,
        tnote5_volume: extracted.tnote5_volume,
        tnote5_open_interest: extracted.tnote5_open_interest,
        // 2-Year T-Note
        tnote2_symbol: extracted.tnote2_symbol,
        tnote2_name: extracted.tnote2_name,
        tnote2_price: extracted.tnote2_price,
        tnote2_market_time: extracted.tnote2_market_time,
        tnote2_change: extracted.tnote2_change,
        tnote2_change_pct: extracted.tnote2_change_pct,
        tnote2_volume: extracted.tnote2_volume,
        tnote2_open_interest: extracted.tnote2_open_interest,
        // Meta
        screenshot_url: screenshotUrl,
        raw_gemini_response: geminiData,
      })
      .select()
      .single();

    if (insertError) {
      console.error("Database insert error:", insertError);
      throw new Error(`DB insert failed: ${insertError.message}`);
    }

    console.log("Successfully inserted premarket data:", insertData.id);

    return new Response(
      JSON.stringify({ success: true, data: insertData }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    console.error("fetch-premarket-futures error:", error);
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    return new Response(
      JSON.stringify({ success: false, error: errorMessage }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
