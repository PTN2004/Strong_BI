import React, { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import ChatInterface from '@/components/chat/ChatInterface';
import { cn } from '@/lib/utils';
import { Settings2, History, X, Clock, BarChart3, Table as TableIcon, Code2, LayoutGrid } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useChat } from '@/contexts/ChatContext';
import ReactECharts from 'echarts-for-react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  getPaginationRowModel,
} from '@tanstack/react-table';
import { Button } from '@/components/ui/button';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

// Sub-component for rendering the Data Table
const DataTable = ({ data }: { data: any[] }) => {
  const columns = useMemo(() => {
    if (!data || data.length === 0) return [];
    return Object.keys(data[0]).map((key) => ({
      header: key,
      accessorKey: key,
    }));
  }, [data]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: 50,
      },
    },
  });

  if (!data || data.length === 0) return (
    <div className="flex items-center justify-center h-full text-muted-foreground/50 text-sm">
      No data available yet.
    </div>
  );

  return (
    <div className="flex flex-col h-full glass-card rounded-3xl border border-white/10 shadow-lg overflow-hidden">
      <div className="flex-1 overflow-auto scrollbar-visible">
        <table className="w-full text-sm text-left">
          <thead className="sticky top-0 bg-background/80 backdrop-blur-xl z-10 border-b border-white/10 shadow-sm">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="px-5 py-4 font-semibold text-foreground/80 whitespace-nowrap uppercase tracking-wider text-[11px]">
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-white/5">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-primary/5 transition-colors duration-200">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-5 py-3 whitespace-nowrap text-foreground/90">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between px-6 py-3 bg-background/40 backdrop-blur-md border-t border-white/10 shrink-0">
        <span className="text-xs font-medium text-muted-foreground">
          Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()} ({data.length} rows)
        </span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-8 text-xs rounded-full bg-transparent border-white/20 hover:bg-white/10" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
            Prev
          </Button>
          <Button variant="outline" size="sm" className="h-8 text-xs rounded-full bg-transparent border-white/20 hover:bg-white/10" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
};

const V2Workspace = () => {
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get('q');
  
  const [isChatProcessing, setIsChatProcessing] = useState(false);
  const [useRulesFromDatabase, setUseRulesFromDatabase] = useState(false);
  const [useMemory, setUseMemory] = useState(true);
  const [showHistory, setShowHistory] = useState(false);
  
  // Track active tab
  const [activeTab, setActiveTab] = useState("visualization");

  const { messages } = useChat();
  const lastSqlMessage = messages.slice().reverse().find(m => m.type === 'sql-query');
  const lastDataMessage = messages.slice().reverse().find(m => m.type === 'query-result');
  const lastChartMessage = messages.slice().reverse().find(m => m.type === 'chart-config' || m.chartConfig);

  // If a chart message has config, we use it. Sometimes it's embedded in the data message.
  const chartConfig = lastChartMessage?.chartConfig || lastDataMessage?.chartConfig;

  return (
    <div className="w-full h-[calc(100vh-56px)] bg-gradient-to-br from-background via-background to-secondary/20 flex flex-row relative overflow-hidden">
      <PanelGroup direction="horizontal" className="w-full h-full">
        
        {/* Left Sidebar - Agent Chat */}
        <Panel defaultSize={60} minSize={40} maxSize={75} className="p-3">
          <div className="w-full h-full flex-shrink-0 bg-white dark:bg-card flex flex-col relative z-20 rounded-3xl overflow-hidden shadow-2xl border border-border/50">
            <div className="p-4 border-b border-border/30 flex items-center justify-between bg-muted/10 shrink-0">
              <div className="flex items-center gap-3">
                <button onClick={() => setShowHistory(!showHistory)} className="text-muted-foreground hover:text-primary transition-colors p-1.5 rounded-md hover:bg-muted">
                  <History className="w-4 h-4" />
                </button>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
                  <h2 className="font-semibold text-sm tracking-wide text-foreground">AI Assistant</h2>
                </div>
              </div>
              <Popover>
                <PopoverTrigger asChild>
                  <button className="text-muted-foreground hover:text-primary transition-colors p-1.5 rounded-md hover:bg-muted">
                    <Settings2 className="w-4 h-4" />
                  </button>
                </PopoverTrigger>
                <PopoverContent align="end" className="w-64 p-4 space-y-4 shadow-xl rounded-xl border-border/50">
                  <div className="space-y-1">
                    <h4 className="font-semibold text-sm">Session Settings</h4>
                    <p className="text-xs text-muted-foreground">Customize assistant behavior.</p>
                  </div>
                  <div className="flex items-center justify-between">
                    <Label htmlFor="use-memory" className="text-xs font-medium">Use Memory</Label>
                    <Switch id="use-memory" checked={useMemory} onCheckedChange={setUseMemory} />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label htmlFor="use-rules" className="text-xs font-medium">Apply Rules</Label>
                    <Switch id="use-rules" checked={useRulesFromDatabase} onCheckedChange={setUseRulesFromDatabase} />
                  </div>
                </PopoverContent>
              </Popover>
            </div>
            
            <div className="flex-1 overflow-hidden relative flex">
              {/* History Drawer Overlay */}
              <div className={cn(
                "absolute inset-y-0 left-0 bg-card/95 backdrop-blur-md border-r border-border/50 w-full z-30 transform transition-transform duration-300 flex flex-col shadow-xl",
                showHistory ? "translate-x-0" : "-translate-x-full"
              )}>
                <div className="p-4 flex items-center justify-between border-b border-border/30">
                  <h3 className="font-semibold text-sm flex items-center gap-2"><Clock className="w-4 h-4 text-primary" /> Session History</h3>
                  <button onClick={() => setShowHistory(false)} className="text-muted-foreground hover:text-foreground p-1 hover:bg-muted rounded">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-1">
                  <div className="text-xs text-muted-foreground italic text-center p-4 bg-muted/30 rounded-lg">Session persistence is currently in development...</div>
                  <div className="text-sm p-3 rounded-lg border border-border/30 hover:border-primary/50 hover:bg-primary/5 cursor-pointer truncate transition-colors">Q2 Revenue Analysis</div>
                  <div className="text-sm p-3 rounded-lg border border-border/30 hover:border-primary/50 hover:bg-primary/5 cursor-pointer truncate transition-colors">Customer Churn Rate</div>
                </div>
              </div>
              
              <div className="flex-1 flex flex-col min-w-0 bg-background/30 backdrop-blur-md">
                <ChatInterface 
                  isChatProcessing={isChatProcessing}
                  onProcessingChange={setIsChatProcessing}
                  useRulesFromDatabase={useRulesFromDatabase}
                  useMemory={useMemory}
                  initialQuery={initialQuery || undefined}
                />
              </div>
            </div>
          </div>
        </Panel>

        <PanelResizeHandle className="w-2 relative group cursor-col-resize z-30 flex items-center justify-center bg-transparent hover:bg-primary/10 transition-colors">
          <div className="w-1 h-12 rounded-full bg-border group-hover:bg-primary/50 transition-colors" />
        </PanelResizeHandle>

        {/* Right Canvas - Main Workspace */}
        <Panel defaultSize={40} minSize={25}>
          <div className="w-full h-full flex flex-col min-w-0 p-4 md:p-6 overflow-hidden">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col h-full overflow-hidden">
            <div className="flex items-center justify-between mb-6 shrink-0">
              <h1 className="text-2xl font-bold text-foreground tracking-tight drop-shadow-sm">Workspace Canvas</h1>
              <TabsList className="glass border border-border/50 shadow-sm p-1 rounded-full">
                <TabsTrigger value="visualization" className="flex items-center gap-2 rounded-full px-4 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md transition-all">
                  <BarChart3 className="w-4 h-4" /> Visualization
                </TabsTrigger>
                <TabsTrigger value="data" className="flex items-center gap-2 rounded-full px-4 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md transition-all">
                  <TableIcon className="w-4 h-4" /> Raw Data
                </TabsTrigger>
                <TabsTrigger value="sql" className="flex items-center gap-2 rounded-full px-4 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md transition-all">
                  <Code2 className="w-4 h-4" /> Generated SQL
                </TabsTrigger>
              </TabsList>
            </div>

            <div className="flex-1 overflow-hidden relative">
              
              {/* Visualization Tab */}
              <TabsContent value="visualization" className="m-0 h-full w-full data-[state=active]:flex flex-col animate-fade-in">
                {chartConfig ? (
                  <div className="flex-1 glass-card rounded-3xl border border-white/10 shadow-lg p-6 overflow-hidden flex flex-col">
                    <ReactECharts 
                      option={{
                        ...(chartConfig.option || chartConfig),
                        backgroundColor: 'transparent',
                        textStyle: { fontFamily: 'Inter, sans-serif' },
                        tooltip: {
                          trigger: 'axis',
                          ...(chartConfig.option?.tooltip || chartConfig.tooltip || {}),
                          backgroundColor: 'rgba(255, 255, 255, 0.95)',
                          borderColor: '#e2e8f0',
                          textStyle: { color: '#0f172a' }
                        }
                      }} 
                      style={{ height: '100%', width: '100%' }}
                      opts={{ renderer: 'canvas' }}
                    />
                  </div>
                ) : (
                  <div className="flex-1 glass-card rounded-3xl border border-white/10 shadow-lg flex flex-col items-center justify-center text-muted-foreground/50 gap-8 relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-secondary/10 opacity-50 group-hover:opacity-80 transition-opacity duration-1000 pointer-events-none" />
                    <div className="w-24 h-24 rounded-[2rem] bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center border border-primary/20 shadow-[0_0_50px_-10px_rgba(var(--primary),0.3)] z-10 relative animate-pulse-glow">
                      <LayoutGrid className="w-12 h-12 text-primary opacity-80" />
                    </div>
                    <div className="text-center z-10 relative space-y-2">
                      <h3 className="text-2xl font-bold text-foreground/90 tracking-tight">Ready to Visualize</h3>
                      <p className="text-base font-medium text-foreground/60 max-w-md mx-auto">Ask the AI assistant a question about your data to generate beautiful insights and charts.</p>
                    </div>
                  </div>
                )}
              </TabsContent>

              {/* Data Tab */}
              <TabsContent value="data" className="m-0 h-full w-full data-[state=active]:flex flex-col animate-fade-in">
                <DataTable data={lastDataMessage?.queryData || []} />
              </TabsContent>

              {/* SQL Tab */}
              <TabsContent value="sql" className="m-0 h-full w-full data-[state=active]:flex flex-col animate-fade-in">
                <div className="flex-1 glass-card rounded-3xl border border-white/10 shadow-lg p-6 overflow-hidden flex flex-col relative">
                  {lastSqlMessage ? (
                    <pre className="flex-1 overflow-auto text-sm font-mono p-6 rounded-lg bg-muted/30 text-primary border border-border/50 select-all whitespace-pre-wrap break-words">
                      {lastSqlMessage.content}
                    </pre>
                  ) : (
                    <div className="flex-1 flex items-center justify-center text-muted-foreground/50 text-base font-medium">
                      Waiting for query generation...
                    </div>
                  )}
                </div>
              </TabsContent>
            </div>
          </Tabs>
        </div>
        </Panel>
      </PanelGroup>
    </div>
  );
};

export default V2Workspace;
