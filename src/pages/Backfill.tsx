import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import TopNavbar from '@/components/TopNavbar';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { Loader2, RefreshCw, Play, Download } from 'lucide-react';

interface EarningsRow {
  ticker: string;
  report_date: string;
  fiscal_period_end: string | null;
  before_after_market: string | null;
}

interface ProcessingRun {
  ticker: string;
  report_date: string;
  timing: string;
  status: string;
  error_message: string | null;
}

const statusColors: Record<string, string> = {
  completed: 'bg-green-900/40 text-green-400 border-green-800',
  pending: 'bg-yellow-900/40 text-yellow-400 border-yellow-800',
  processing: 'bg-blue-900/40 text-blue-400 border-blue-800',
  failed: 'bg-red-900/40 text-red-400 border-red-800',
};

const Backfill = () => {
  const [fromDate, setFromDate] = useState('2026-01-11');
  const [toDate, setToDate] = useState('2026-02-09');
  const [fetchResult, setFetchResult] = useState<string | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Fetch earnings in the date range
  const { data: earnings = [], isLoading: earningsLoading, refetch: refetchEarnings } = useQuery({
    queryKey: ['backfill-earnings', fromDate, toDate],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('earnings_calendar')
        .select('ticker, report_date, fiscal_period_end, before_after_market')
        .gte('report_date', fromDate)
        .lte('report_date', toDate)
        .order('report_date', { ascending: true })
        .order('ticker', { ascending: true });
      if (error) throw error;
      return (data || []) as EarningsRow[];
    },
  });

  // Fetch processing runs for the date range
  const { data: runs = [], refetch: refetchRuns } = useQuery({
    queryKey: ['backfill-runs', fromDate, toDate],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('excel_processing_runs')
        .select('ticker, report_date, timing, status, error_message')
        .gte('report_date', fromDate)
        .lte('report_date', toDate);
      if (error) throw error;
      return (data || []) as ProcessingRun[];
    },
    refetchInterval: 10000,
  });

  // Map runs by ticker+report_date for quick lookup
  const runsMap = useMemo(() => {
    const map = new Map<string, ProcessingRun>();
    runs.forEach(r => map.set(`${r.ticker}_${r.report_date}`, r));
    return map;
  }, [runs]);

  // Merged view
  const tableRows = useMemo(() => {
    return earnings.map(e => {
      const run = runsMap.get(`${e.ticker}_${e.report_date}`);
      return {
        ...e,
        status: run?.status || 'not started',
        error_message: run?.error_message || null,
        timing: e.before_after_market === 'BeforeMarket' ? 'premarket' : 'afterhours',
      };
    });
  }, [earnings, runsMap]);

  // Progress summary
  const summary = useMemo(() => {
    const total = tableRows.length;
    const completed = tableRows.filter(r => r.status === 'completed').length;
    const failed = tableRows.filter(r => r.status === 'failed').length;
    const pending = tableRows.filter(r => r.status === 'pending' || r.status === 'processing').length;
    const remaining = total - completed - failed - pending;
    return { total, completed, failed, pending, remaining };
  }, [tableRows]);

  // Fetch earnings from EODHD
  const fetchEarningsMutation = useMutation({
    mutationFn: async () => {
      const response = await supabase.functions.invoke('backfill-earnings', {
        body: { from_date: fromDate, to_date: toDate },
      });
      if (response.error) throw response.error;
      return response.data;
    },
    onSuccess: (data) => {
      setFetchResult(`Fetched ${data.matchedRecords} matched records (${data.insertedRecords} upserted)`);
      toast({ title: 'Earnings fetched', description: `${data.insertedRecords} records upserted` });
      refetchEarnings();
      refetchRuns();
    },
    onError: (error) => {
      toast({ title: 'Error fetching earnings', description: String(error), variant: 'destructive' });
    },
  });

  // Trigger single ticker
  const triggerMutation = useMutation({
    mutationFn: async (row: { ticker: string; report_date: string; fiscal_period_end: string | null; timing: string }) => {
      const response = await supabase.functions.invoke('backfill-trigger-single', {
        body: row,
      });
      if (response.error) throw response.error;
      return response.data;
    },
    onSuccess: (data) => {
      toast({ title: 'Processing triggered', description: `${data.ticker} queued` });
      queryClient.invalidateQueries({ queryKey: ['backfill-runs'] });
    },
    onError: (error) => {
      toast({ title: 'Trigger failed', description: String(error), variant: 'destructive' });
    },
  });

  const handleRefresh = () => {
    refetchEarnings();
    refetchRuns();
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNavbar />
      <main className="container mx-auto px-4 py-8 md:px-6 space-y-6">
        <h1 className="text-2xl font-bold text-foreground">Backfill Dashboard</h1>

        {/* Section 1: Fetch Earnings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Download className="h-5 w-5" />
              Fetch Historical Earnings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="text-sm text-muted-foreground">From</label>
                <Input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="w-44" />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">To</label>
                <Input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="w-44" />
              </div>
              <Button
                onClick={() => fetchEarningsMutation.mutate()}
                disabled={fetchEarningsMutation.isPending}
              >
                {fetchEarningsMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Fetch Earnings
              </Button>
            </div>
            {fetchResult && <p className="text-sm text-muted-foreground">{fetchResult}</p>}
          </CardContent>
        </Card>

        {/* Section 2: Progress Summary */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          {[
            { label: 'Total', value: summary.total },
            { label: 'Completed', value: summary.completed },
            { label: 'In Progress', value: summary.pending },
            { label: 'Failed', value: summary.failed },
            { label: 'Not Started', value: summary.remaining },
          ].map(s => (
            <Card key={s.label}>
              <CardContent className="pt-4 pb-4 text-center">
                <div className="text-2xl font-bold text-foreground">{s.value}</div>
                <div className="text-xs text-muted-foreground">{s.label}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Section 3: Ticker Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Tickers ({tableRows.length})</CardTitle>
              <Button variant="ghost" size="sm" onClick={handleRefresh}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {earningsLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : tableRows.length === 0 ? (
              <p className="text-center text-sm text-muted-foreground py-8">
                No earnings data found. Click "Fetch Earnings" to populate.
              </p>
            ) : (
              <div className="max-h-[600px] overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ticker</TableHead>
                      <TableHead>Report Date</TableHead>
                      <TableHead>Fiscal Period End</TableHead>
                      <TableHead>Timing</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tableRows.map((row, i) => (
                      <TableRow key={`${row.ticker}-${row.report_date}-${i}`}>
                        <TableCell className="font-medium">{row.ticker}</TableCell>
                        <TableCell>{row.report_date}</TableCell>
                        <TableCell>{row.fiscal_period_end || '—'}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">
                            {row.timing}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={statusColors[row.status] || 'bg-secondary text-secondary-foreground'}
                          >
                            {row.status}
                          </Badge>
                          {row.error_message && (
                            <p className="text-xs text-destructive mt-1 max-w-xs truncate" title={row.error_message}>
                              {row.error_message}
                            </p>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={row.status === 'completed' || row.status === 'pending' || row.status === 'processing' || triggerMutation.isPending}
                            onClick={() => triggerMutation.mutate({
                              ticker: row.ticker,
                              report_date: row.report_date,
                              fiscal_period_end: row.fiscal_period_end,
                              timing: row.timing,
                            })}
                          >
                            <Play className="mr-1 h-3 w-3" />
                            Process
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default Backfill;
