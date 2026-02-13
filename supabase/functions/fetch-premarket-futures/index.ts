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

    // Step 1: Use Firecrawl to screenshot CNBC premarket page
    console.log("Step 1: Calling Firecrawl to screenshot CNBC...");
    const firecrawlResponse = await fetch("https://api.firecrawl.dev/v1/scrape", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${FIRECRAWL_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url: "https://www.cnbc.com/",
        actions: [
          { type: "wait", milliseconds: 3000 },
          { type: "click", selector: "button.MarketsBannerMenu-marketOption[aria-controls='Homepage-MarketsBanner-1-panel']" },
          { type: "wait", milliseconds: 2000 },
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
              "You are a precise data extraction assistant. You will be given a screenshot of the CNBC homepage showing premarket futures data. Extract ONLY the three futures indices: DOW FUT, S&P FUT, and NAS FUT. For each, extract the price, nominal change, percent change, direction (up or down), and the last updated timestamp shown. Be extremely precise with the numbers.",
          },
          {
            role: "user",
            content: [
              {
                type: "text",
                text: "Extract the premarket futures data from this CNBC screenshot. I need DOW FUT, S&P FUT, and NAS FUT data including price, change, percent change, direction (up/down), and the last updated timestamp.",
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
              description: "Extract premarket futures data from CNBC screenshot",
              parameters: {
                type: "object",
                properties: {
                  dow_price: { type: "number", description: "DOW Futures price" },
                  dow_change: { type: "number", description: "DOW Futures nominal change (positive or negative)" },
                  dow_change_pct: { type: "number", description: "DOW Futures percent change (positive or negative)" },
                  dow_direction: { type: "string", enum: ["up", "down"], description: "DOW Futures direction" },
                  sp500_price: { type: "number", description: "S&P 500 Futures price" },
                  sp500_change: { type: "number", description: "S&P 500 Futures nominal change (positive or negative)" },
                  sp500_change_pct: { type: "number", description: "S&P 500 Futures percent change (positive or negative)" },
                  sp500_direction: { type: "string", enum: ["up", "down"], description: "S&P 500 Futures direction" },
                  nas_price: { type: "number", description: "Nasdaq Futures price" },
                  nas_change: { type: "number", description: "Nasdaq Futures nominal change (positive or negative)" },
                  nas_change_pct: { type: "number", description: "Nasdaq Futures percent change (positive or negative)" },
                  nas_direction: { type: "string", enum: ["up", "down"], description: "Nasdaq Futures direction" },
                  last_updated: { type: "string", description: "Last updated timestamp as shown on CNBC (e.g. 'LAST | 11:15:31 AM EST')" },
                },
                required: [
                  "dow_price", "dow_change", "dow_change_pct", "dow_direction",
                  "sp500_price", "sp500_change", "sp500_change_pct", "sp500_direction",
                  "nas_price", "nas_change", "nas_change_pct", "nas_direction",
                  "last_updated",
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
        dow_price: extracted.dow_price,
        dow_change: extracted.dow_change,
        dow_change_pct: extracted.dow_change_pct,
        dow_direction: extracted.dow_direction,
        sp500_price: extracted.sp500_price,
        sp500_change: extracted.sp500_change,
        sp500_change_pct: extracted.sp500_change_pct,
        sp500_direction: extracted.sp500_direction,
        nas_price: extracted.nas_price,
        nas_change: extracted.nas_change,
        nas_change_pct: extracted.nas_change_pct,
        nas_direction: extracted.nas_direction,
        last_updated: extracted.last_updated,
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
