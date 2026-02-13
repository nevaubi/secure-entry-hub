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

    // Step 2: Send screenshot to Gemini for structured extraction
    console.log("Step 2: Sending screenshot to Gemini for extraction...");
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
              "You are a precise data extraction assistant. You will be given a screenshot of Yahoo Finance's futures/commodities page showing a table of futures contracts. Extract data for exactly three futures: YM=F (Mini Dow Jones), ES=F (E-Mini S&P 500), and NQ=F (Nasdaq 100). The table has columns: Symbol, Name, Price, Market Time, Change, Change %, Volume, Open Interest. Be extremely precise with the numbers. Store volume and open interest as text exactly as displayed (e.g. '1.061M', '95,915').",
          },
          {
            role: "user",
            content: [
              {
                type: "text",
                text: "Extract futures data from this Yahoo Finance screenshot. Find the rows for YM=F (Dow), ES=F (S&P 500), and NQ=F (Nasdaq 100). For each, extract: symbol, name, price, market time, change, change %, volume, and open interest.",
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
              description: "Extract futures data from Yahoo Finance screenshot for Dow (YM=F), S&P 500 (ES=F), and Nasdaq 100 (NQ=F)",
              parameters: {
                type: "object",
                properties: {
                  dow_symbol: { type: "string", description: "Dow symbol, e.g. 'YM=F'" },
                  dow_name: { type: "string", description: "Dow contract name, e.g. 'Mini Dow Jones Indus.-$5 Jun 25'" },
                  dow_price: { type: "number", description: "Dow futures price" },
                  dow_market_time: { type: "string", description: "Dow market time, e.g. '11:37AM EST'" },
                  dow_change: { type: "number", description: "Dow nominal change (positive or negative)" },
                  dow_change_pct: { type: "number", description: "Dow percent change (positive or negative)" },
                  dow_volume: { type: "string", description: "Dow volume as displayed, e.g. '95,915'" },
                  dow_open_interest: { type: "string", description: "Dow open interest as displayed, e.g. '69,303'" },
                  sp500_symbol: { type: "string", description: "S&P 500 symbol, e.g. 'ES=F'" },
                  sp500_name: { type: "string", description: "S&P 500 contract name, e.g. 'E-Mini S&P 500 Jun 25'" },
                  sp500_price: { type: "number", description: "S&P 500 futures price" },
                  sp500_market_time: { type: "string", description: "S&P 500 market time" },
                  sp500_change: { type: "number", description: "S&P 500 nominal change (positive or negative)" },
                  sp500_change_pct: { type: "number", description: "S&P 500 percent change (positive or negative)" },
                  sp500_volume: { type: "string", description: "S&P 500 volume as displayed, e.g. '1.061M'" },
                  sp500_open_interest: { type: "string", description: "S&P 500 open interest as displayed, e.g. '1.895M'" },
                  nas_symbol: { type: "string", description: "Nasdaq symbol, e.g. 'NQ=F'" },
                  nas_name: { type: "string", description: "Nasdaq contract name, e.g. 'Nasdaq 100 Jun 25'" },
                  nas_price: { type: "number", description: "Nasdaq futures price" },
                  nas_market_time: { type: "string", description: "Nasdaq market time" },
                  nas_change: { type: "number", description: "Nasdaq nominal change (positive or negative)" },
                  nas_change_pct: { type: "number", description: "Nasdaq percent change (positive or negative)" },
                  nas_volume: { type: "string", description: "Nasdaq volume as displayed, e.g. '448,483'" },
                  nas_open_interest: { type: "string", description: "Nasdaq open interest as displayed, e.g. '269,452'" },
                },
                required: [
                  "dow_symbol", "dow_name", "dow_price", "dow_market_time", "dow_change", "dow_change_pct", "dow_volume", "dow_open_interest",
                  "sp500_symbol", "sp500_name", "sp500_price", "sp500_market_time", "sp500_change", "sp500_change_pct", "sp500_volume", "sp500_open_interest",
                  "nas_symbol", "nas_name", "nas_price", "nas_market_time", "nas_change", "nas_change_pct", "nas_volume", "nas_open_interest",
                ],
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

    // Step 3: Insert into database
    console.log("Step 3: Inserting into recurring_premarket_data...");
    const { data: insertData, error: insertError } = await supabase
      .from("recurring_premarket_data")
      .insert({
        captured_at: new Date().toISOString(),
        dow_symbol: extracted.dow_symbol,
        dow_name: extracted.dow_name,
        dow_price: extracted.dow_price,
        dow_market_time: extracted.dow_market_time,
        dow_change: extracted.dow_change,
        dow_change_pct: extracted.dow_change_pct,
        dow_volume: extracted.dow_volume,
        dow_open_interest: extracted.dow_open_interest,
        sp500_symbol: extracted.sp500_symbol,
        sp500_name: extracted.sp500_name,
        sp500_price: extracted.sp500_price,
        sp500_market_time: extracted.sp500_market_time,
        sp500_change: extracted.sp500_change,
        sp500_change_pct: extracted.sp500_change_pct,
        sp500_volume: extracted.sp500_volume,
        sp500_open_interest: extracted.sp500_open_interest,
        nas_symbol: extracted.nas_symbol,
        nas_name: extracted.nas_name,
        nas_price: extracted.nas_price,
        nas_market_time: extracted.nas_market_time,
        nas_change: extracted.nas_change,
        nas_change_pct: extracted.nas_change_pct,
        nas_volume: extracted.nas_volume,
        nas_open_interest: extracted.nas_open_interest,
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
