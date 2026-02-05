 import { useState } from "react";
 import { Button } from "@/components/ui/button";
 import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
 import { Progress } from "@/components/ui/progress";
 import { supabase } from "@/integrations/supabase/client";
 
 // CSV data parsed and embedded
 import companiesCSV from "@/data/companies_rows.csv?raw";
 
 interface Company {
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
 
 function parseCSV(csvText: string): Company[] {
   const lines = csvText.trim().split("\n");
   const companies: Company[] = [];
   
   // Skip header line
   for (let i = 1; i < lines.length; i++) {
     const line = lines[i];
     if (!line.trim()) continue;
     
     // Parse CSV with quoted fields
     const values: string[] = [];
     let current = "";
     let inQuotes = false;
     
     for (let j = 0; j < line.length; j++) {
       const char = line[j];
       if (char === '"') {
         inQuotes = !inQuotes;
       } else if (char === "," && !inQuotes) {
         values.push(current);
         current = "";
       } else {
         current += char;
       }
     }
     values.push(current);
     
     if (values.length >= 9) {
       companies.push({
         company_id: parseInt(values[0]) || 0,
         ticker: values[1] || "",
         name: values[2] || "",
         cik: values[3] ? parseInt(values[3]) : null,
         exchange: values[4] || null,
         sector: values[5] || null,
         description: values[6] || null,
         year_founded: values[7] ? parseInt(values[7]) : null,
         logo_url: values[8] || null,
       });
     }
   }
   
   return companies;
 }
 
 export default function ImportCompanies() {
   const [importing, setImporting] = useState(false);
   const [progress, setProgress] = useState(0);
   const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
 
   const importCompanies = async () => {
     setImporting(true);
     setProgress(0);
     setResult(null);
 
     try {
       const companies = parseCSV(companiesCSV);
       console.log(`Parsed ${companies.length} companies from CSV`);
       
       // Split into batches of 500 for the edge function
       const batchSize = 500;
       let totalImported = 0;
 
       for (let i = 0; i < companies.length; i += batchSize) {
         const batch = companies.slice(i, i + batchSize);
         
         const { data, error } = await supabase.functions.invoke("import-companies", {
           body: { companies: batch },
         });
 
         if (error) {
           throw new Error(`Batch ${Math.floor(i / batchSize) + 1} failed: ${error.message}`);
         }
 
         totalImported += batch.length;
         setProgress((totalImported / companies.length) * 100);
         console.log(`Imported ${totalImported}/${companies.length}`);
       }
 
       setResult({ success: true, message: `Successfully imported ${totalImported} companies!` });
     } catch (error) {
       console.error("Import error:", error);
       setResult({ 
         success: false, 
         message: error instanceof Error ? error.message : "Unknown error occurred" 
       });
     } finally {
       setImporting(false);
     }
   };
 
   return (
     <div className="min-h-screen flex items-center justify-center bg-background p-4">
       <Card className="w-full max-w-md">
         <CardHeader>
           <CardTitle>Import Companies</CardTitle>
           <CardDescription>
             Import 3,135 company records from CSV into the database
           </CardDescription>
         </CardHeader>
         <CardContent className="space-y-4">
           {importing && (
             <div className="space-y-2">
               <Progress value={progress} />
               <p className="text-sm text-muted-foreground text-center">
                 Importing... {Math.round(progress)}%
               </p>
             </div>
           )}
 
           {result && (
             <div
               className={`p-3 rounded-md ${
                 result.success
                   ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                   : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
               }`}
             >
               {result.message}
             </div>
           )}
 
           <Button 
             onClick={importCompanies} 
             disabled={importing}
             className="w-full"
           >
             {importing ? "Importing..." : "Start Import"}
           </Button>
         </CardContent>
       </Card>
     </div>
   );
 }