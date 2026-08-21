import React, { useMemo, useEffect, useState, useCallback } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  MarkerType,
  MiniMap
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { Table2, Box, BrainCircuit, ChevronDown, ChevronUp } from 'lucide-react';

interface SchemaNode {
  id: number;
  userId: string;
  name: string;
  label?: string;
  description?: string;
  formula?: string;
  columns?: Array<string | { name: string; type?: string; dataType?: string }>;
}

interface SchemaLink {
  source: number;
  target: number;
}

interface SchemaData {
  nodes: SchemaNode[];
  links: SchemaLink[];
  nodesMap: Map<number, SchemaNode>;
}

interface ERDiagramViewerProps {
  schemaData: SchemaData;
  theme: string;
}

// Custom Node Component
const CustomTableNode = ({ data, selected }: any) => {
  const { node, isExpanded, toggleExpand, theme } = data;
  const isMetric = node.label === 'Metric';
  const isDimension = node.label === 'Dimension';
  const isSemantic = isMetric || isDimension;

  const maxColumns = 8;
  const columns = node.columns || [];
  const displayColumns = isExpanded ? columns : columns.slice(0, maxColumns);
  const hasMore = !isExpanded && columns.length > maxColumns;

  let headerColor = theme === 'light' ? 'bg-blue-600' : 'bg-blue-700';
  let Icon = Table2;
  
  if (isMetric) {
    headerColor = theme === 'light' ? 'bg-amber-500' : 'bg-amber-600';
    Icon = BrainCircuit;
  } else if (isDimension) {
    headerColor = theme === 'light' ? 'bg-emerald-500' : 'bg-emerald-600';
    Icon = Box;
  }

  return (
    <div 
      className={`rounded-md shadow-lg border-2 ${selected ? 'border-blue-400 ring-2 ring-blue-400/50' : (theme === 'light' ? 'border-slate-300' : 'border-slate-700')} overflow-hidden flex flex-col`}
      style={{
        width: 250,
        backgroundColor: theme === 'light' ? '#f8fafc' : '#1e293b',
        color: theme === 'light' ? '#0f172a' : '#f1f5f9',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      
      {/* Header */}
      <div className={`${headerColor} px-3 py-2 flex items-center justify-between text-white`}>
        <div className="flex items-center gap-2 overflow-hidden">
          <Icon className="w-4 h-4 shrink-0" />
          <span className="font-semibold text-sm truncate">{node.name}</span>
        </div>
        {!isSemantic && (
          <span className="text-xs opacity-75 font-mono">TABLE</span>
        )}
      </div>

      {/* Body */}
      <div className="flex flex-col text-sm divide-y divide-border/10">
        {isSemantic ? (
          <div className="p-3 flex flex-col gap-2">
            {node.description && (
              <div className="text-xs opacity-80">{node.description}</div>
            )}
            {node.formula && (
              <div className="text-xs font-mono bg-black/5 dark:bg-white/5 p-2 rounded">
                {node.formula}
              </div>
            )}
          </div>
        ) : (
          <>
            {displayColumns.map((col: any, idx: number) => {
              const colName = typeof col === 'string' ? col : col.name;
              return (
                <div key={idx} className="px-3 py-1.5 flex items-center justify-between hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                  <span className="font-mono text-xs truncate">{colName}</span>
                </div>
              );
            })}
            
            {columns.length > maxColumns && (
              <div 
                className="px-3 py-2 text-xs text-blue-500 hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer flex items-center justify-center gap-1 font-medium bg-black/5 dark:bg-white/5"
                onClick={(e) => {
                  e.stopPropagation();
                  toggleExpand(node.id);
                }}
              >
                {isExpanded ? (
                  <>
                    <ChevronUp className="w-3 h-3" />
                    Collapse
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-3 h-3" />
                    {columns.length - maxColumns} more columns
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>
      
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
};

const nodeTypes = {
  customTable: CustomTableNode,
};

// Dagre Layout Algorithm
const getLayoutedElements = (nodes: any[], edges: any[], direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({ 
    rankdir: direction, 
    align: 'UL',
    nodesep: 80,
    edgesep: 20,
    ranksep: 200,
    marginx: 50,
    marginy: 50,
  });

  nodes.forEach((node) => {
    // Estimating node sizes since we don't have exact dimensions until render
    let height = 36 + (node.data.isExpanded ? (node.data.node.columns?.length || 0) : Math.min(8, node.data.node.columns?.length || 0)) * 32;
    if (node.data.node.columns?.length > 8) height += 32; // toggle button
    if (node.data.node.label === 'Metric' || node.data.node.label === 'Dimension') height = 150;
    
    dagreGraph.setNode(node.id, { width: 250, height });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    // Shift target position to center of node
    node.targetPosition = isHorizontal ? Position.Left : Position.Top;
    node.sourcePosition = isHorizontal ? Position.Right : Position.Bottom;
    node.position = {
      x: nodeWithPosition.x - 250 / 2,
      y: nodeWithPosition.y - nodeWithPosition.height / 2,
    };
  });

  return { nodes, edges };
};

export const ERDiagramViewer = ({ schemaData, theme }: ERDiagramViewerProps) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set());

  const toggleExpand = useCallback((nodeId: number) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  // Effect to rebuild nodes and edges when data or expanded state changes
  useEffect(() => {
    if (!schemaData || !schemaData.nodes || schemaData.nodes.length === 0) return;

    const initialNodes = schemaData.nodes.map((node) => {
      return {
        id: String(node.id),
        type: 'customTable',
        position: { x: 0, y: 0 },
        data: { 
          node, 
          isExpanded: expandedNodes.has(node.id),
          toggleExpand,
          theme
        },
      };
    });

    const initialEdges = schemaData.links.map((link, idx) => {
      let stroke = theme === 'light' ? '#94a3b8' : '#475569';
      
      const sourceNode = schemaData.nodesMap.get(link.source);
      if (sourceNode?.label === 'Metric') stroke = theme === 'light' ? '#fbbf24' : '#b45309';
      else if (sourceNode?.label === 'Dimension') stroke = theme === 'light' ? '#34d399' : '#047857';

      return {
        id: `e${link.source}-${link.target}-${idx}`,
        source: String(link.source),
        target: String(link.target),
        type: 'smoothstep', // Orthogonal routing with rounded corners
        animated: false,
        style: { stroke, strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 15,
          height: 15,
          color: stroke,
        },
      };
    });

    // Run layout algorithm
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      initialNodes,
      initialEdges,
      'LR' // Left to Right layout
    );

    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [schemaData, theme, expandedNodes, toggleExpand, setNodes, setEdges]);

  return (
    <div className="w-full h-full" style={{ background: theme === 'light' ? '#ffffff' : '#0f172a' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-right"
        minZoom={0.1}
        maxZoom={1.5}
      >
        <Background 
          color={theme === 'light' ? '#cbd5e1' : '#334155'} 
          gap={16} 
          size={1} 
        />
        <Controls 
          className={theme === 'light' ? 'bg-white' : 'bg-slate-800'}
        />
        <MiniMap 
          nodeColor={(n) => {
            const isMetric = n.data?.node?.label === 'Metric';
            const isDim = n.data?.node?.label === 'Dimension';
            if (isMetric) return theme === 'light' ? '#f59e0b' : '#d97706';
            if (isDim) return theme === 'light' ? '#10b981' : '#059669';
            return theme === 'light' ? '#3b82f6' : '#2563eb';
          }}
          maskColor={theme === 'light' ? 'rgba(255, 255, 255, 0.6)' : 'rgba(15, 23, 42, 0.6)'}
          style={{
            backgroundColor: theme === 'light' ? '#f8fafc' : '#1e293b'
          }}
        />
      </ReactFlow>
    </div>
  );
};
