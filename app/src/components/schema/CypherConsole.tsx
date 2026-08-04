import { useState } from 'react';
import { DatabaseService } from '@/services/database';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { useDatabase } from '@/contexts/DatabaseContext';

export const CypherConsole = () => {
  const [query, setQuery] = useState('MATCH (n) RETURN n LIMIT 10');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const { selectedGraph } = useDatabase();
  const { toast } = useToast();

  const handleExecute = async () => {
    if (!selectedGraph) return;
    setLoading(true);
    try {
      const data = await DatabaseService.executeCypher(selectedGraph.id, query);
      setResults(data.results || []);
    } catch (err: any) {
      toast({ title: 'Query Failed', description: err.message, variant: 'destructive' });
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full space-y-4 p-4 border rounded-xl bg-card">
      <div className="flex flex-col space-y-2 shrink-0">
        <label className="text-sm font-bold text-muted-foreground">Cypher Query Console</label>
        <Textarea 
          value={query} 
          onChange={(e) => setQuery(e.target.value)} 
          className="font-mono h-32 bg-background border-border text-foreground"
          placeholder="MATCH (n) RETURN n LIMIT 10"
        />
        <div className="flex justify-end">
          <Button onClick={handleExecute} disabled={loading || !selectedGraph} className="w-32">
            {loading ? 'Executing...' : 'Run Query'}
          </Button>
        </div>
      </div>
      <div className="flex-1 overflow-auto bg-muted/50 p-4 rounded-xl border border-border">
        <h3 className="text-xs font-semibold mb-2 text-muted-foreground uppercase tracking-wider">Results</h3>
        {results.length > 0 ? (
          <pre className="text-xs font-mono text-foreground">{JSON.stringify(results, null, 2)}</pre>
        ) : (
          <div className="text-sm text-muted-foreground flex h-full items-center justify-center italic">No results to display</div>
        )}
      </div>
    </div>
  );
};
