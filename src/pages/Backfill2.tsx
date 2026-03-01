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
import { Loader2, RefreshCw, Play, MoreVertical, CheckCircle, XCircle, RotateCcw } from 'lucide-react';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const statusColors: Record<string, string> = {
  completed: 'bg-green-900/40 text-green-400 border-green-800',
  pending: 'bg-yellow-900/40 text-yellow-400 border-yellow-800',
  processing: 'bg-blue-900/40 text-blue-400 border-blue-800',
  failed: 'bg-red-900/40 text-red-400 border-red-800',
};

const Backfill2 = () => {
  const [ticker, setTicker] = useState('');
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Fetch all standardized processing runs
  const { data: runs = [], isLoading, refetch } = useQuery({
    queryKey: ['standardized-runs'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('standardized_processing_runs')
        .select('*')
        .order('created_at', { ascending: false });
      if (error) throw error;
      return data || [];
    },
    refetchInterval: 10000,
  });

  // Summary stats
  const summary = useMemo(() => {
    const total = runs.length;
    const completed = runs.filter(r => r.status === 'completed').length;
    const failed = runs.filter(r => r.status === 'failed').length;
    const inProgress = runs.filter(r => r.status === 'pending' || r.status === 'processing').length;
    return { total, completed, failed, inProgress };
  }, [runs]);

  // Trigger standardized agent
  const triggerMutation = useMutation({
    mutationFn: async (tickerValue: string) => {
      const response = await supabase.functions.invoke('trigger-standardized-agent', {
        body: { ticker: tickerValue.toUpperCase().trim() },
      });
      if (response.error) throw response.error;
      return response.data;
    },
    onSuccess: (data) => {
      toast({ title: 'Processing triggered', description: `${data?.ticker || ticker.toUpperCase()} queued` });
      setTicker('');
      queryClient.invalidateQueries({ queryKey: ['standardized-runs'] });
    },
    onError: (error) => {
      toast({ title: 'Trigger failed', description: String(error), variant: 'destructive' });
    },
  });

  // Update status mutation
  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: string }) => {
      const { error } = await supabase
        .from('standardized_processing_runs')
        .update({
          status,
          completed_at: new Date().toISOString(),
          error_message: status === 'failed' ? 'Manually marked as failed' : null,
        })
        .eq('id', id);
      if (error) throw error;
    },
    onSuccess: () => {
      toast({ title: 'Status updated' });
      refetch();
    },
    onError: (error) => {
      toast({ title: 'Update failed', description: String(error), variant: 'destructive' });
    },
  });

  // Delete run mutation
  const deleteRunMutation = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase
        .from('standardized_processing_runs')
        .delete()
        .eq('id', id);
      if (error) throw error;
    },
    onSuccess: () => {
      toast({ title: 'Run deleted' });
      refetch();
    },
    onError: (error) => {
      toast({ title: 'Delete failed', description: String(error), variant: 'destructive' });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim()) return;
    triggerMutation.mutate(ticker);
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNavbar />
      <main className="container mx-auto px-4 py-8 md:px-6 space-y-6">
        <h1 className="text-2xl font-bold text-foreground">Standardized Agent</h1>

        {/* Trigger Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Play className="h-5 w-5" />
              Trigger Processing
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="flex items-end gap-4">
              <div className="flex-1 max-w-xs">
                <label className="text-sm text-muted-foreground">Ticker</label>
                <Input
                  placeholder="e.g. AAPL"
                  value={ticker}
                  onChange={e => setTicker(e.target.value)}
                  className="uppercase"
                />
              </div>
              <Button type="submit" disabled={triggerMutation.isPending || !ticker.trim()}>
                {triggerMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Process
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Summary Stats */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: 'Total', value: summary.total },
            { label: 'Completed', value: summary.completed },
            { label: 'In Progress', value: summary.inProgress },
            { label: 'Failed', value: summary.failed },
          ].map(s => (
            <Card key={s.label}>
              <CardContent className="pt-4 pb-4 text-center">
                <div className="text-2xl font-bold text-foreground">{s.value}</div>
                <div className="text-xs text-muted-foreground">{s.label}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Runs Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Processing Runs ({runs.length})</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => refetch()}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : runs.length === 0 ? (
              <p className="text-center text-sm text-muted-foreground py-8">
                No processing runs yet. Enter a ticker above to get started.
              </p>
            ) : (
              <div className="max-h-[600px] overflow-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ticker</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Files Updated</TableHead>
                      <TableHead>Started</TableHead>
                      <TableHead>Completed</TableHead>
                      <TableHead>Error</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runs.map((run) => (
                      <TableRow key={run.id}>
                        <TableCell className="font-medium">{run.ticker}</TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={statusColors[run.status] || 'bg-secondary text-secondary-foreground'}
                          >
                            {run.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{run.files_updated ?? '—'}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {run.started_at ? new Date(run.started_at).toLocaleString() : '—'}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {run.completed_at ? new Date(run.completed_at).toLocaleString() : '—'}
                        </TableCell>
                        <TableCell>
                          {run.error_message ? (
                            <p className="text-xs text-destructive max-w-xs truncate" title={run.error_message}>
                              {run.error_message}
                            </p>
                          ) : '—'}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={run.status === 'pending' || run.status === 'processing' || triggerMutation.isPending}
                              onClick={() => triggerMutation.mutate(run.ticker)}
                            >
                              <Play className="mr-1 h-3 w-3" />
                              Re-run
                            </Button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                  <MoreVertical className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="bg-popover">
                                <DropdownMenuItem
                                  onClick={() => updateStatusMutation.mutate({ id: run.id, status: 'completed' })}
                                >
                                  <CheckCircle className="mr-2 h-4 w-4 text-green-500" />
                                  Mark Completed
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => updateStatusMutation.mutate({ id: run.id, status: 'failed' })}
                                >
                                  <XCircle className="mr-2 h-4 w-4 text-red-500" />
                                  Mark Failed
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => deleteRunMutation.mutate(run.id)}
                                >
                                  <RotateCcw className="mr-2 h-4 w-4" />
                                  Delete Run
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
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

export default Backfill2;
