 import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
 
 const corsHeaders = {
   'Access-Control-Allow-Origin': '*',
   'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
 };
 
 // Storage buckets to check (12 total)
 const STORAGE_BUCKETS = [
   // As-Reported
   'financials-annual-income',
   'financials-quarterly-income',
   'financials-annual-balance',
   'financials-quarterly-balance',
   'financials-annual-cashflow',
   'financials-quarterly-cashflow',
   // Standardized
   'standardized-annual-income',
   'standardized-quarterly-income',
   'standardized-annual-balance',
   'standardized-quarterly-balance',
   'standardized-annual-cashflow',
   'standardized-quarterly-cashflow',
 ];
 
 // Get current date in Central Time (America/Chicago)
 function getCentralTimeDate(): string {
   const now = new Date();
   const centralTime = new Intl.DateTimeFormat('en-CA', {
     timeZone: 'America/Chicago',
     year: 'numeric',
     month: '2-digit',
     day: '2-digit',
   }).format(now);
   return centralTime; // Returns YYYY-MM-DD format
 }
 
 interface FileCheckResult {
   bucket: string;
   exists: boolean;
   size?: number;
   error?: string;
 }
 
 async function checkFileInBucket(
   externalSupabaseUrl: string,
   bucket: string,
   ticker: string
 ): Promise<FileCheckResult> {
   const fileName = `${ticker}.xlsx`;
   const fileUrl = `${externalSupabaseUrl}/storage/v1/object/public/${bucket}/${fileName}`;
   
   try {
     const response = await fetch(fileUrl, { method: 'HEAD' });
     
     if (response.ok) {
       const contentLength = response.headers.get('content-length');
       return {
         bucket,
         exists: true,
         size: contentLength ? parseInt(contentLength, 10) : undefined,
       };
     } else if (response.status === 404) {
       return {
         bucket,
         exists: false,
       };
     } else {
       return {
         bucket,
         exists: false,
         error: `HTTP ${response.status}: ${response.statusText}`,
       };
     }
   } catch (error) {
     return {
       bucket,
       exists: false,
       error: error instanceof Error ? error.message : 'Unknown error',
     };
   }
 }
 
 Deno.serve(async (req) => {
   // Handle CORS preflight
   if (req.method === 'OPTIONS') {
     return new Response(null, { headers: corsHeaders });
   }
 
   try {
     // Get environment variables
     const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
     const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
     const externalSupabaseUrl = Deno.env.get('EXTERNAL_SUPABASE_URL');
     
     if (!externalSupabaseUrl) {
       throw new Error('EXTERNAL_SUPABASE_URL not configured');
     }
 
     const supabase = createClient(supabaseUrl, supabaseServiceKey);
 
     // Parse request body for parameters
     let timing: string | null = null;
     let overrideDate: string | null = null;
     let specificTicker: string | null = null;
 
     if (req.method === 'POST') {
       try {
         const body = await req.json();
         timing = body.timing || null;
         overrideDate = body.date || null;
         specificTicker = body.ticker || null;
       } catch {
         // Empty body is OK for cron triggers
       }
     }
 
     // Get the date to process
     const reportDate = overrideDate || getCentralTimeDate();
     console.log(`Processing earnings files for date: ${reportDate}, timing: ${timing || 'all'}`);
 
     // Build query for earnings_calendar
     let query = supabase
       .from('earnings_calendar')
       .select('ticker, before_after_market')
       .eq('report_date', reportDate);
 
     // Apply timing filter
     if (timing === 'premarket') {
       query = query.eq('before_after_market', 'BeforeMarket');
     } else if (timing === 'afterhours') {
       query = query.or('before_after_market.eq.AfterMarket,before_after_market.is.null');
     }
 
     // Apply specific ticker filter if provided
     if (specificTicker) {
       query = query.eq('ticker', specificTicker);
     }
 
     const { data: earningsData, error: queryError } = await query;
 
     if (queryError) {
       throw new Error(`Database query error: ${queryError.message}`);
     }
 
     if (!earningsData || earningsData.length === 0) {
       return new Response(
         JSON.stringify({
           success: true,
           message: 'No earnings found for the specified criteria',
           date: reportDate,
           timing: timing || 'all',
           tickersProcessed: 0,
           filesChecked: 0,
           filesFound: 0,
         }),
         { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
       );
     }
 
     const tickers = [...new Set(earningsData.map(e => e.ticker))];
     console.log(`Found ${tickers.length} tickers to process: ${tickers.join(', ')}`);
 
     // Process each ticker
     const allResults: Array<{
       ticker: string;
       report_date: string;
       bucket_name: string;
       file_exists: boolean;
       file_size_bytes: number | null;
       processed_at: string;
       status: string;
       error_message: string | null;
     }> = [];
 
     let totalFilesFound = 0;
 
     for (const ticker of tickers) {
       console.log(`Checking files for ticker: ${ticker}`);
       
       // Check all 12 buckets in parallel for this ticker
       const bucketChecks = STORAGE_BUCKETS.map(bucket => 
         checkFileInBucket(externalSupabaseUrl, bucket, ticker)
       );
       
       const results = await Promise.all(bucketChecks);
       
       for (const result of results) {
         if (result.exists) {
           totalFilesFound++;
         }
         
         allResults.push({
           ticker,
           report_date: reportDate,
           bucket_name: result.bucket,
           file_exists: result.exists,
           file_size_bytes: result.size || null,
           processed_at: new Date().toISOString(),
           status: result.error ? 'error' : (result.exists ? 'found' : 'not_found'),
           error_message: result.error || null,
         });
       }
     }
 
     console.log(`Total files checked: ${allResults.length}, files found: ${totalFilesFound}`);
 
     // Upsert all results to the tracking table
     const { error: upsertError } = await supabase
       .from('earnings_file_processing')
       .upsert(allResults, {
         onConflict: 'ticker,report_date,bucket_name',
         ignoreDuplicates: false,
       });
 
     if (upsertError) {
       throw new Error(`Upsert error: ${upsertError.message}`);
     }
 
     // Build summary
     const summary = {
       success: true,
       message: 'File processing completed',
       date: reportDate,
       timing: timing || 'all',
       tickersProcessed: tickers.length,
       filesChecked: allResults.length,
       filesFound: totalFilesFound,
       filesMissing: allResults.length - totalFilesFound,
       tickers: tickers.map(ticker => {
         const tickerResults = allResults.filter(r => r.ticker === ticker);
         const found = tickerResults.filter(r => r.file_exists).length;
         return {
           ticker,
           filesFound: found,
           filesMissing: 12 - found,
         };
       }),
     };
 
     return new Response(
       JSON.stringify(summary),
       { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
     );
 
   } catch (error) {
     console.error('Error in process-earnings-files:', error);
     const errorMessage = error instanceof Error ? error.message : 'Unknown error';
     return new Response(
       JSON.stringify({
         success: false,
         error: errorMessage,
       }),
       { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
     );
   }
 });