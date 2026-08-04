import { useEffect, useRef, useState, useCallback } from 'react';
import type { Data, FalkorDBCanvas } from '@falkordb/canvas';
import { ZoomIn, ZoomOut, Locate, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useDatabase } from '@/contexts/DatabaseContext';
import { DatabaseService } from '@/services/database';
import { useToast } from '@/components/ui/use-toast';

export const GraphDataExplorer = () => {
  const canvasRef = useRef<FalkorDBCanvas>(null);
  const [data, setData] = useState<{ nodes: any[]; edges: any[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const { selectedGraph } = useDatabase();
  const { toast } = useToast();

  const [theme, setTheme] = useState<string>(() => {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  });

  useEffect(() => {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
          const newTheme = document.documentElement.getAttribute('data-theme') || 'dark';
          setTheme(newTheme);
        }
      });
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  const [canvasLoaded, setCanvasLoaded] = useState(false);
  useEffect(() => {
    import('@falkordb/canvas').then(() => {
      setCanvasLoaded(true);
    });
  }, []);

  useEffect(() => {
    if (selectedGraph) {
      loadData();
    }
  }, [selectedGraph]);

  const loadData = async () => {
    if (!selectedGraph) return;
    setLoading(true);
    try {
      const result = await DatabaseService.exploreGraph(selectedGraph.id, 150);
      setData(result);
    } catch (error) {
      console.error('Failed to load graph data:', error);
      toast({ title: "Failed to load data", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const convertToCanvasData = useCallback((data: any): Data => {
    let nodeIndex = 1;
    const oldToNew = new Map<any, number>();

    const nodes = data.nodes.flatMap((raw: any) => {
      // Handle Neo4j ({"n": Node}), FalkorDB ({"data": [Node]}), or plain object
      let items = [];
      if (raw.n) items = [raw.n];
      else if (raw.data && Array.isArray(raw.data)) items = raw.data;
      else items = [raw];

      return items.map((n: any) => {
        const id = n.id ?? n.element_id ?? n.identity ?? n._id ?? nodeIndex++;
        oldToNew.set(id, id);
        
        let labels = n.labels ?? (n.label ? [n.label] : n.alias ? [n.alias] : ['Node']);
        if (!Array.isArray(labels)) labels = [labels];
        
        return {
          id,
          labels,
          visible: true,
          color: theme === 'light' ? '#3b82f6' : '#60a5fa',
          data: n.properties ?? n,
        };
      });
    });

    let edgeIndex = 1;
    const links = data.edges.flatMap((raw: any) => {
      let items = [];
      if (raw.r) items = [raw.r];
      else if (raw.data && Array.isArray(raw.data)) items = raw.data;
      else items = [raw];

      return items.map((e: any) => {
        const source = e.start_node ?? e.startNodeElementId ?? e.source ?? e.start ?? e.src_node;
        const target = e.end_node ?? e.endNodeElementId ?? e.target ?? e.end ?? e.dest_node;
        return {
          id: e.id ?? e.element_id ?? e.identity ?? e._id ?? edgeIndex++,
          source: oldToNew.get(source) ?? source,
          target: oldToNew.get(target) ?? target,
          relationship: e.type ?? e.relation ?? e.relationship ?? 'LINK',
          visible: true,
          color: theme === 'light' ? '#cbd5e1' : '#475569',
          data: e.properties ?? e,
        };
      });
    }).filter((link: any) => link.source !== undefined && link.target !== undefined);

    return { nodes, links };
  }, [theme]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data || data.nodes.length === 0) return;

    const canvasData = convertToCanvasData(data);
    
    canvas.setConfig({
      autoStopOnSettle: true,
    });
    
    canvas.setBackgroundColor(theme === 'light' ? '#ffffff' : '#191919');
    canvas.setForegroundColor(theme === 'light' ? '#111' : '#f5f5f5');
    canvas.setData(canvasData);

  }, [data, theme, canvasLoaded, convertToCanvasData]);

  const handleZoomIn = () => canvasRef.current?.zoom(canvasRef.current.getZoom() * 1.2);
  const handleZoomOut = () => canvasRef.current?.zoom(canvasRef.current.getZoom() / 1.2);
  const handleCenter = () => canvasRef.current?.zoomToFit(1.5);

  return (
    <div className="flex flex-col h-full border rounded-xl bg-card overflow-hidden">
      <div className="flex items-center justify-between p-2 border-b border-border bg-muted/30 shrink-0">
        <span className="text-sm font-bold text-muted-foreground px-2">Knowledge Graph Explorer</span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadData} title="Refresh" className="h-8 w-8 p-0">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={handleZoomIn} title="Zoom In" className="h-8 w-8 p-0">
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={handleZoomOut} title="Zoom Out" className="h-8 w-8 p-0">
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={handleCenter} title="Center" className="h-8 w-8 p-0">
            <Locate className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="flex-1 relative bg-background">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
            <div className="text-muted-foreground text-sm font-medium animate-pulse">Loading graph data...</div>
          </div>
        )}
        {!loading && canvasLoaded && data && data.nodes.length > 0 && (
          <falkordb-canvas ref={canvasRef} node-mode='replace' class="block w-full h-full" style={{ width: '100%', height: '100%', display: 'block' }} />
        )}
        {!loading && (!data || data.nodes.length === 0) && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-muted-foreground">
              <p>No data nodes available</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
