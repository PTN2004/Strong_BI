import React, { useEffect, useState, useCallback } from 'react';
import { 
  ReactFlow, 
  Background, 
  Controls, 
  MiniMap, 
  useNodesState, 
  useEdgesState, 
  MarkerType,
  Handle,
  Position,
  Panel,
  ReactFlowProvider
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';

import { X, Network, Maximize, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useDatabase } from '@/contexts/DatabaseContext';
import { DatabaseService } from '@/services/database';
import { useToast } from '@/components/ui/use-toast';
import { buildApiUrl } from '@/config/api';

// --- Custom Nodes ---

// 1. Table Node (Green theme)
const TableNode = ({ data }: any) => {
  return (
    <div className="bg-white dark:bg-[#0f172a] border-2 border-emerald-500 rounded-xl shadow-lg min-w-[220px] overflow-hidden flex flex-col font-sans">
      <Handle type="target" position={Position.Top} className="w-2 h-2 bg-emerald-500 border-none" />
      <div className="bg-emerald-50 dark:bg-emerald-950/30 border-b border-emerald-100 dark:border-emerald-900/50 p-3 flex items-center justify-between">
        <span className="font-bold text-emerald-700 dark:text-emerald-400 text-sm tracking-tight">{data.label}</span>
        <span className="text-[9px] uppercase font-bold text-emerald-500/70 bg-emerald-100 dark:bg-emerald-900/30 px-1.5 py-0.5 rounded">Table</span>
      </div>
      <div className="p-2 flex flex-col gap-1.5 bg-white dark:bg-[#0f172a]">
        {data.columns?.map((col: any, idx: number) => {
          const colName = typeof col === 'string' ? col : col.name;
          const colType = typeof col === 'string' ? '' : (col.dataType || col.type || '');
          return (
            <div key={idx} className="flex justify-between items-center text-[11px] px-2 py-1 rounded bg-gray-50 dark:bg-gray-900/50 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors group">
              <span className="font-semibold text-gray-700 dark:text-gray-300 group-hover:text-emerald-600 dark:group-hover:text-emerald-400">{colName}</span>
              <span className="text-gray-400 dark:text-gray-500 font-mono text-[9px]">{colType}</span>
            </div>
          );
        })}
        {(!data.columns || data.columns.length === 0) && (
          <div className="text-[11px] text-gray-400 text-center italic py-1">No columns</div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 bg-emerald-500 border-none" />
    </div>
  );
};

// 2. Metric Node (Yellow theme)
const MetricNode = ({ data }: any) => {
  return (
    <div className="bg-white dark:bg-[#0f172a] border-2 border-amber-500 rounded-xl shadow-lg min-w-[180px] overflow-hidden flex flex-col font-sans">
      <Handle type="target" position={Position.Top} className="w-2 h-2 bg-amber-500 border-none" />
      <div className="bg-amber-50 dark:bg-amber-950/30 p-3 flex items-center justify-between">
        <span className="font-bold text-amber-700 dark:text-amber-400 text-sm tracking-tight">{data.label}</span>
        <span className="text-[9px] uppercase font-bold text-amber-500/70 bg-amber-100 dark:bg-amber-900/30 px-1.5 py-0.5 rounded">Metric</span>
      </div>
      {data.expr && (
        <div className="px-3 py-2 bg-white dark:bg-[#0f172a] border-t border-amber-100 dark:border-amber-900/30">
          <p className="text-[10px] text-gray-500 dark:text-gray-400 font-mono break-all">{data.expr}</p>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 bg-amber-500 border-none" />
    </div>
  );
};

// 3. Dimension Node (Purple theme)
const DimensionNode = ({ data }: any) => {
  return (
    <div className="bg-white dark:bg-[#0f172a] border-2 border-purple-500 rounded-xl shadow-lg min-w-[180px] overflow-hidden flex flex-col font-sans">
      <Handle type="target" position={Position.Top} className="w-2 h-2 bg-purple-500 border-none" />
      <div className="bg-purple-50 dark:bg-purple-950/30 p-3 flex items-center justify-between">
        <span className="font-bold text-purple-700 dark:text-purple-400 text-sm tracking-tight">{data.label}</span>
        <span className="text-[9px] uppercase font-bold text-purple-500/70 bg-purple-100 dark:bg-purple-900/30 px-1.5 py-0.5 rounded">Dim</span>
      </div>
      {data.expr && (
        <div className="px-3 py-2 bg-white dark:bg-[#0f172a] border-t border-purple-100 dark:border-purple-900/30">
          <p className="text-[10px] text-gray-500 dark:text-gray-400 font-mono break-all">{data.expr}</p>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 bg-purple-500 border-none" />
    </div>
  );
};

const nodeTypes = {
  table: TableNode,
  metric: MetricNode,
  dimension: DimensionNode,
};

// --- DAGRE LAYOUT ---
const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const getLayoutedElements = (nodes: any[], edges: any[], direction = 'TB') => {
  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({ rankdir: direction, nodesep: 100, ranksep: 120 });

  nodes.forEach((node) => {
    // Estimate node size based on type and content
    let width = 220;
    let height = 150;
    if (node.type === 'metric' || node.type === 'dimension') {
      width = 180;
      height = 80;
    } else if (node.type === 'table') {
      const cols = node.data.columns?.length || 0;
      height = 40 + (cols * 24); // header + cols
    }
    dagreGraph.setNode(node.id, { width, height });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      // Shift node to center based on width/height
      position: {
        x: nodeWithPosition.x - nodeWithPosition.width / 2,
        y: nodeWithPosition.y - nodeWithPosition.height / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

// --- MAIN COMPONENT ---
interface SchemaViewerProps {
  isOpen: boolean;
  onClose: () => void;
  graphId: string;
}

const SchemaViewerFlow = ({ graphId, onClose }: { graphId: string, onClose: () => void }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const { selectedGraph } = useDatabase();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch Tables from Schema
      const schemaData = await DatabaseService.getGraphData(graphId);
      
      // Fetch Metrics/Dimensions from Semantic Layer
      let semanticData: any = { metrics: [], dimensions: [] };
      try {
        const semanticResponse = await fetch(buildApiUrl(`/graphs/${graphId}/semantic`), { credentials: 'include' });
        if (semanticResponse.ok) {
          const sData = await semanticResponse.json();
          semanticData = sData || { metrics: [], dimensions: [] };
        }
      } catch (e) {
        console.warn("Could not load semantic data", e);
      }

      const newNodes: any[] = [];
      const newEdges: any[] = [];

      // 1. Process Tables
      const tablesMap = new Map<string, string>(); // name to node id
      if (schemaData && schemaData.nodes) {
        schemaData.nodes.forEach((node: any, idx: number) => {
          const nodeId = `table-${node.id || idx}`;
          tablesMap.set(node.name.toLowerCase(), nodeId);
          newNodes.push({
            id: nodeId,
            type: 'table',
            data: { label: node.name, columns: node.columns || [] },
            position: { x: 0, y: 0 },
          });
        });

        // Edges for foreign keys (if available in schemaData.links)
        if (schemaData.links) {
          schemaData.links.forEach((link: any, idx: number) => {
            const sourceNode = schemaData.nodes.find((n:any) => n.id === link.source || n.userId === link.source);
            const targetNode = schemaData.nodes.find((n:any) => n.id === link.target || n.userId === link.target);
            if (sourceNode && targetNode) {
              const sourceId = `table-${sourceNode.id || schemaData.nodes.indexOf(sourceNode)}`;
              const targetId = `table-${targetNode.id || schemaData.nodes.indexOf(targetNode)}`;
              newEdges.push({
                id: `edge-tbl-${idx}`,
                source: sourceId,
                target: targetId,
                animated: true,
                style: { stroke: '#94a3b8', strokeWidth: 1.5, strokeDasharray: '5,5' },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
              });
            }
          });
        }
      }

      // 2. Process Metrics
      if (semanticData.metrics) {
        semanticData.metrics.forEach((metric: any, idx: number) => {
          const nodeId = `metric-${idx}`;
          newNodes.push({
            id: nodeId,
            type: 'metric',
            data: { label: metric.name, expr: metric.expr || metric.sql || metric.description },
            position: { x: 0, y: 0 },
          });
          
          // Connect to related table if inferred from expression
          const exprLower = (metric.expr || metric.sql || '').toLowerCase();
          for (const [tblName, tblId] of tablesMap.entries()) {
            if (exprLower.includes(tblName)) {
              newEdges.push({
                id: `edge-met-${idx}-${tblId}`,
                source: tblId,
                target: nodeId,
                animated: false,
                style: { stroke: '#f59e0b', strokeWidth: 2 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#f59e0b' },
              });
            }
          }
        });
      }

      // 3. Process Dimensions
      if (semanticData.dimensions) {
        semanticData.dimensions.forEach((dim: any, idx: number) => {
          const nodeId = `dim-${idx}`;
          newNodes.push({
            id: nodeId,
            type: 'dimension',
            data: { label: dim.name, expr: dim.expr || dim.sql || dim.description },
            position: { x: 0, y: 0 },
          });

          // Connect to related table
          const exprLower = (dim.expr || dim.sql || '').toLowerCase();
          for (const [tblName, tblId] of tablesMap.entries()) {
            if (exprLower.includes(tblName)) {
              newEdges.push({
                id: `edge-dim-${idx}-${tblId}`,
                source: tblId,
                target: nodeId,
                animated: false,
                style: { stroke: '#8b5cf6', strokeWidth: 2 },
                markerEnd: { type: MarkerType.ArrowClosed, color: '#8b5cf6' },
              });
            }
          }
        });
      }

      // Auto Layout
      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(newNodes, newEdges, 'TB');
      setNodes(layoutedNodes);
      setEdges(layoutedEdges);

    } catch (e: any) {
      toast({ title: "Failed to load Schema", description: e.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [graphId, toast, setNodes, setEdges]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onLayout = useCallback(() => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(nodes, edges, 'TB');
    setNodes([...layoutedNodes]);
    setEdges([...layoutedEdges]);
  }, [nodes, edges, setNodes, setEdges]);

  return (
    <div className="w-full h-full relative bg-gray-50/50 dark:bg-[#020617]">
      {loading ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 dark:bg-black/80 z-50">
          <Loader2 className="w-10 h-10 animate-spin text-blue-500 mb-4" />
          <p className="text-sm font-semibold text-gray-500">Generating Schema Diagram...</p>
        </div>
      ) : (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          attributionPosition="bottom-right"
          minZoom={0.1}
        >
          <Background color="#cbd5e1" gap={20} size={1.5} />
          <Controls className="bg-white dark:bg-gray-800 shadow-lg border-none rounded-xl overflow-hidden" />
          <MiniMap 
            className="bg-white dark:bg-gray-800 shadow-xl rounded-xl border border-gray-100 dark:border-gray-700" 
            nodeColor={(n: any) => {
              if (n.type === 'table') return '#10b981';
              if (n.type === 'metric') return '#f59e0b';
              if (n.type === 'dimension') return '#8b5cf6';
              return '#ccc';
            }} 
            maskColor="rgba(0,0,0,0.1)"
          />
          <Panel position="top-left" className="m-4">
            <div className="bg-white/90 dark:bg-black/80 backdrop-blur p-4 rounded-2xl shadow-xl border border-gray-200/50 dark:border-gray-800/50 flex flex-col gap-2">
              <h3 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <Network className="w-4 h-4 text-blue-500" />
                Schema Diagram
              </h3>
              <p className="text-[10px] text-gray-500 max-w-[200px]">Interactive Entity-Relationship & Semantic graph.</p>
              
              <div className="flex flex-col gap-1.5 mt-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                <div className="flex items-center gap-2 text-xs font-semibold text-emerald-600"><span className="w-2.5 h-2.5 rounded bg-emerald-500"></span> Table</div>
                <div className="flex items-center gap-2 text-xs font-semibold text-amber-500"><span className="w-2.5 h-2.5 rounded bg-amber-500"></span> Metric</div>
                <div className="flex items-center gap-2 text-xs font-semibold text-purple-500"><span className="w-2.5 h-2.5 rounded bg-purple-500"></span> Dimension</div>
              </div>
              
              <Button size="sm" variant="outline" className="mt-2 h-8 text-xs" onClick={onLayout}>
                <RefreshCw className="w-3 h-3 mr-1" /> Auto Layout
              </Button>
            </div>
          </Panel>
          <Panel position="top-right" className="m-4">
            <Button size="icon" variant="secondary" onClick={onClose} className="rounded-full shadow-lg h-10 w-10 hover:bg-red-50 hover:text-red-600">
              <X className="w-5 h-5" />
            </Button>
          </Panel>
        </ReactFlow>
      )}
    </div>
  );
};

// Wrapper Component that uses absolute overlay instead of whatever the old SchemaViewer did
const SchemaViewer = ({ isOpen, onClose, graphId }: SchemaViewerProps) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex animate-in fade-in duration-200">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full h-full lg:m-6 lg:rounded-[24px] overflow-hidden bg-white dark:bg-black shadow-2xl border border-gray-200/50 dark:border-gray-800 flex flex-col">
        <ReactFlowProvider>
          <SchemaViewerFlow graphId={graphId} onClose={onClose} />
        </ReactFlowProvider>
      </div>
    </div>
  );
};

export default SchemaViewer;
