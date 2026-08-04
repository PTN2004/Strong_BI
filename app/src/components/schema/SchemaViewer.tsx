import { useEffect, useRef, useState, useCallback } from 'react';
import type { Data, FalkorDBCanvas, GraphNode } from '@falkordb/canvas';
import { ZoomIn, ZoomOut, Locate, X, GripVertical } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useDatabase } from '@/contexts/DatabaseContext';
import { DatabaseService } from '@/services/database';
import { useToast } from '@/components/ui/use-toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CypherConsole } from './CypherConsole';
import { GraphDataExplorer } from './GraphDataExplorer';

interface SchemaNode {
  id: number;
  userId: string;
  name: string;
  columns: Array<string | { name: string; type?: string; dataType?: string }>;
}

interface SchemaLink {
  source: number;
  target: number;
}

interface SchemaData {
  nodes: SchemaNode[];
  links: SchemaLink[];
  nodesMap: Map<number, SchemaNode>
}

interface SchemaViewerProps {
  isOpen: boolean;
  onClose: () => void;
  onWidthChange?: (width: number) => void;
  sidebarWidth?: number;
  side?: 'left' | 'right';
}

const SchemaViewer = ({ isOpen, onClose, onWidthChange, sidebarWidth = 64, side = 'left' }: SchemaViewerProps) => {
  const canvasRef = useRef<FalkorDBCanvas>(null);
  const resizeRef = useRef<HTMLDivElement>(null);
  const [schemaData, setSchemaData] = useState<SchemaData | null>(null);
  const [loading, setLoading] = useState(false);
  const { selectedGraph } = useDatabase();
  const { toast } = useToast();

  const [activeTab, setActiveTab] = useState("schema");

  // Track current theme for canvas colors
  const [theme, setTheme] = useState<string>(() => {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  });

  // Listen for theme changes
  useEffect(() => {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
          const newTheme = document.documentElement.getAttribute('data-theme') || 'dark';
          setTheme(newTheme);
        }
      });
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });

    return () => observer.disconnect();
  }, []);

  const NODE_WIDTH = 260;
  const MIN_WIDTH = 400;
  const MAX_WIDTH_PERCENT = 0.9;
  const DEFAULT_WIDTH_PERCENT = 0.7;

  const [width, setWidth] = useState(() => {
    const initialWidth = Math.floor(window.innerWidth * DEFAULT_WIDTH_PERCENT);
    return initialWidth;
  });
  const [isResizing, setIsResizing] = useState(false);
  const [canvasLoaded, setCanvasLoaded] = useState(false);

  // Notify parent of width changes
  useEffect(() => {
    if (onWidthChange) {
      onWidthChange(width);
    }
  }, [width, onWidthChange]);

  // Load falkordb-canvas dynamically
  useEffect(() => {
    import('@falkordb/canvas').then(() => {
      setCanvasLoaded(true);
    });
  }, []);

  useEffect(() => {
    if (isOpen && selectedGraph) {
      loadSchemaData();
    }
  }, [isOpen, selectedGraph]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;

      const newWidth = side === 'right' 
        ? window.innerWidth - e.clientX
        : e.clientX - sidebarWidth;
      const maxWidth = Math.floor(window.innerWidth * MAX_WIDTH_PERCENT);

      if (newWidth >= MIN_WIDTH && newWidth <= maxWidth) {
        setWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, sidebarWidth, side]);

  const loadSchemaData = async () => {
    if (!selectedGraph) return;

    setLoading(true);
    try {
      const data = await DatabaseService.getGraphData(selectedGraph.id);

      // Create a mapping from old IDs to new IDs
      const oldIdToNewId = new Map<string, number>();

      // Remap nodes with new sequential IDs
      data.nodes = data.nodes.map((node, index) => {
        const newId = index + 1;
        oldIdToNewId.set(node.id, newId);
        return {
          ...node,
          userId: node.id,
          id: newId,
        };
      });

      // Update links to use the new node IDs
      data.links = data.links
        .map((link) => ({
          source: oldIdToNewId.get(link.source)!,
          target: oldIdToNewId.get(link.target)!,
        }))
        .filter((link) => link.source !== undefined && link.target !== undefined);

      const remapNodesMap = new Map<number, SchemaNode>();
      data.nodes.forEach((node) => {
        remapNodesMap.set(node.id, node);
      });

      setSchemaData({
        nodes: data.nodes,
        links: data.links,
        nodesMap: remapNodesMap,
      });
    } catch (error) {
      console.error('Failed to load schema data:', error);
      toast({
        title: "Failed to load Schema",
        description: "Could not retrieve schema data from the database.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const convertToCanvasData = useCallback((data: SchemaData): Data => {
    return {
      nodes: data.nodes.map((node) => ({
        id: node.id,
        labels: [node.name],
        visible: true,
        color: theme === 'light' ? '#3b82f6' : '#60a5fa',
        data: {},
      })),
      links: data.links.map((link, index) => ({
        id: index + 1,
        source: link.source,
        target: link.target,
        relationship: 'HAS',
        visible: true,
        color: theme === 'light' ? '#cbd5e1' : '#475569',
        data: {},
      })),
    };
  }, [theme]);

  const handleZoomIn = () => {
    if (canvasRef.current) {
      const currentZoom = canvasRef.current.getZoom();
      canvasRef.current.zoom(currentZoom * 1.2);
    }
  };

  const handleZoomOut = () => {
    if (canvasRef.current) {
      const currentZoom = canvasRef.current.getZoom();
      canvasRef.current.zoom(currentZoom / 1.2);
    }
  };

  const handleCenter = () => {
    canvasRef.current?.zoomToFit(1.5);
  };

  // Set up canvas configuration and data - MUST be in single effect to ensure proper order
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !schemaData) return;

    const nodeCanvasObject = (node: GraphNode, ctx: CanvasRenderingContext2D) => {
      const schemaNode = schemaData.nodesMap.get(Number(node.id));

      if (!schemaNode) return;

      const columns = schemaNode.columns || [];
      const lineHeight = 18;
      const padding = 12;
      const headerHeight = 28;
      const nodeHeight = headerHeight + columns.length * lineHeight + padding * 2;

      ctx.fillStyle = theme === 'light' ? '#f1f5f9' : '#1e293b';
      ctx.strokeStyle = theme === 'light' ? '#cbd5e1' : '#475569';
      ctx.lineWidth = 1;

      ctx.beginPath();
      ctx.roundRect(
        (node.x || 0) - NODE_WIDTH / 2,
        (node.y || 0) - nodeHeight / 2,
        NODE_WIDTH,
        nodeHeight,
        8
      );
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = theme === 'light' ? '#3b82f6' : '#60a5fa';
      ctx.beginPath();
      ctx.roundRect(
        (node.x || 0) - NODE_WIDTH / 2,
        (node.y || 0) - nodeHeight / 2,
        NODE_WIDTH,
        headerHeight,
        [8, 8, 0, 0]
      );
      ctx.fill();

      ctx.fillStyle = theme === 'light' ? '#0f172a' : '#ffffff';
      ctx.font = 'bold 13px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(
        schemaNode.name,
        node.x || 0,
        (node.y || 0) - nodeHeight / 2 + headerHeight / 2
      );

      ctx.font = '12px JetBrains Mono, monospace';
      const columnTextColor = theme === 'light' ? '#0f172a' : '#f8fafc';
      const typeTextColor = theme === 'light' ? '#64748b' : '#94a3b8';
      let colY = (node.y || 0) - nodeHeight / 2 + headerHeight + padding + 8;
      const startX = (node.x || 0) - NODE_WIDTH / 2 + padding;

      columns.forEach((col: any) => {
        let name = col;
        let type = null;
        if (typeof col === 'object') {
          name = col.name || '';
          type = col.type || col.dataType || null;
        }

        ctx.textAlign = 'left';
        ctx.fillStyle = columnTextColor;
        ctx.fillText(name, startX, colY);

        if (type) {
          ctx.fillStyle = typeTextColor;
          const nameWidth = ctx.measureText(name).width;
          const available = NODE_WIDTH - padding * 2 - nameWidth - 8;
          let typeText = String(type);
          if (available > 0) {
            if (ctx.measureText(typeText).width > available) {
              while (
                typeText.length > 0 &&
                ctx.measureText(typeText + '…').width > available
              ) {
                typeText = typeText.slice(0, -1);
              }
              typeText = typeText + '…';
            }
            ctx.textAlign = 'right';
            ctx.fillText(typeText, (node.x || 0) + NODE_WIDTH / 2 - padding, colY);
          }
          ctx.fillStyle = columnTextColor;
          ctx.textAlign = 'left';
        }

        colY += lineHeight;
      });
    };

    const nodePointerAreaPaint = (node: GraphNode, color: string, ctx: CanvasRenderingContext2D) => {
      const schemaNode = schemaData.nodesMap.get(Number(node.id));

      if (!schemaNode) return;

      const columns = schemaNode.columns || [];
      const lineHeight = 14;
      const padding = 8;
      const headerHeight = 20;
      const nodeHeight = headerHeight + columns.length * lineHeight + padding * 2;

      ctx.fillStyle = color;
      const areaPadding = 5;
      ctx.fillRect(
        (node.x || 0) - NODE_WIDTH / 2 - areaPadding,
        (node.y || 0) - nodeHeight / 2 - areaPadding,
        NODE_WIDTH + areaPadding * 2,
        nodeHeight + areaPadding * 2
      );
    };

    const canvasData = convertToCanvasData(schemaData);

    canvas.setConfig({
      autoStopOnSettle: false,
      node: {
        nodeCanvasObject,
        nodePointerAreaPaint,
      }
    });
    
    canvas.setBackgroundColor(theme === 'light' ? '#ffffff' : '#191919');
    canvas.setForegroundColor(theme === 'light' ? '#111' : '#f5f5f5');
    canvas.setData(canvasData);

    // Adjust graph physics to prevent large table nodes from clumping
    setTimeout(() => {
      const graph = canvas.getGraph();
      if (graph) {
        // Increase repulsion force significantly for large nodes
        graph.d3Force('charge')?.strength(-2000);
        // Increase the default distance between connected nodes
        graph.d3Force('link')?.distance(250);
        
        // Reheat simulation to apply the new forces
        if (typeof graph.d3ReheatSimulation === 'function') {
          graph.d3ReheatSimulation();
        }
      }
    }, 100);
  }, [schemaData, theme, canvasLoaded, convertToCanvasData]);

  if (!isOpen) return null;

  const isRightSide = side === 'right';

  return (
    <>
      {/* Mobile overlay backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40 md:hidden"
        onClick={onClose}
      />

      {/* Schema Viewer */}
      <div
        data-testid="schema-panel"
        className={`fixed top-0 h-full bg-background border-l border-r border-border flex flex-col transition-all duration-300
          ${isOpen ? 'translate-x-0' : isRightSide ? 'translate-x-full' : '-translate-x-full'}
          ${isOpen ? 'pointer-events-auto' : 'pointer-events-none'}
          md:z-30 z-50
          w-[80vw] max-w-[400px] md:max-w-none
        `}
        style={{
          ...(window.innerWidth >= 768 ? {
            ...(isRightSide 
              ? { right: 0, left: 'auto', width: `${width}px` } 
              : { left: `${sidebarWidth}px`, width: `${width}px` }
            )
          } : {})
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border shrink-0">
          <h2 className="text-lg font-semibold text-foreground">Database Explorer</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="px-4 py-2 border-b border-border shrink-0">
            <TabsList className="w-full grid grid-cols-3">
              <TabsTrigger value="schema">Schema</TabsTrigger>
              <TabsTrigger value="explore">Data Graph</TabsTrigger>
              <TabsTrigger value="cypher">Cypher</TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="schema" className="flex-1 m-0 data-[state=active]:flex flex-col min-h-0 relative outline-none">
            {/* Controls */}
            <div className="flex gap-2 p-2 border-b border-border shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={handleZoomIn}
                className="h-8 w-8 p-0 bg-card border-border text-muted-foreground hover:bg-foreground"
                title="Zoom In"
              >
                <ZoomIn className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleZoomOut}
                className="h-8 w-8 p-0 bg-card border-border text-muted-foreground hover:bg-foreground"
                title="Zoom Out"
              >
                <ZoomOut className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCenter}
                className="h-8 w-8 p-0 bg-card border-border text-muted-foreground hover:bg-foreground"
                title="Center"
              >
                <Locate className="h-4 w-4" />
              </Button>
            </div>

            {/* Graph Container */}
            <div className="flex-1 w-full bg-background relative overflow-hidden">
              {loading && (
                <div className="flex items-center justify-center h-full">
                  <div className="text-muted-foreground">Loading schema...</div>
                </div>
              )}
              {!loading && canvasLoaded && schemaData && schemaData.nodes.length > 0 && (
                <falkordb-canvas ref={canvasRef} node-mode='replace' class="block w-full h-full" style={{ width: '100%', height: '100%', display: 'block' }} />
              )}
              {!loading && (!schemaData || schemaData.nodes.length === 0) && (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center text-muted-foreground">
                    <p>No schema data available</p>
                    <p className="text-sm mt-2">
                      {!selectedGraph ? 'Select a database first' : 'This database has no schema data'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="explore" className="flex-1 m-0 data-[state=active]:flex flex-col min-h-0 relative outline-none p-4 overflow-auto">
            <GraphDataExplorer />
          </TabsContent>

          <TabsContent value="cypher" className="flex-1 m-0 data-[state=active]:flex flex-col min-h-0 relative outline-none p-4 overflow-auto">
            <CypherConsole />
          </TabsContent>
        </Tabs>

        {/* Resize Handle */}
        <div
          ref={resizeRef}
          className={`absolute top-0 w-1 h-full cursor-ew-resize hover:bg-purple-500 transition-colors z-50
            ${isRightSide ? 'left-0' : 'right-0'}
          `}
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsResizing(true);
          }}
        >
          <div className={`absolute top-1/2 -translate-y-1/2 -translate-x-1/2 ${isRightSide ? 'left-0' : 'right-0'}`}>
            <GripVertical className="h-4 w-4 text-border" />
          </div>
        </div>
      </div>
    </>
  );
};

export default SchemaViewer;
