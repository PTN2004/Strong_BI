import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useDatabase } from '@/contexts/DatabaseContext';
import { useSettings } from '@/contexts/SettingsContext';
import { useToast } from '@/components/ui/use-toast';
import { Search, Brain, Table as TableIcon, LayoutDashboard, Loader2, Code, ChevronRight, CheckCircle2, AlertCircle, BarChart3, Network, Sparkles } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ChatService } from '@/services/chat';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import vietnamMap from '../../assets/maps/vietnam.json';
import worldMap from '../../assets/maps/world.json';

try {
  echarts.registerMap('vietnam', vietnamMap as any);
  echarts.registerMap('world', worldMap as any);
} catch (e) {
  console.error("Failed to register maps", e);
}
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  getPaginationRowModel,
} from '@tanstack/react-table';

const DataTable = ({ data }: { data: any[] }) => {
  const columns = useMemo(() => {
    if (!data || data.length === 0) return [];
    return Object.keys(data[0]).map((key) => ({
      header: key,
      accessorKey: key,
      cell: (info: any) => {
        const val = info.getValue();
        if (typeof val === 'number') {
          const keyLower = key.toLowerCase();
          // Bỏ qua format cho ID hoặc Năm
          if (keyLower === 'id' || keyLower.endsWith('_id') || keyLower.includes('year') || keyLower.includes('năm')) {
            return val;
          }
          
          // Format theo chuẩn US (dấu phẩy cho phần nghìn) để dễ đọc
          return new Intl.NumberFormat('en-US', {
            maximumFractionDigits: 2
          }).format(val);
        }
        return val;
      }
    }));
  }, [data]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: 10,
      },
    },
  });

  if (!data || data.length === 0) return (
    <div className="flex items-center justify-center p-8 text-muted-foreground/50 text-sm border rounded-lg bg-card/50">
      No data available to display in table.
    </div>
  );

  return (
    <div className="flex flex-col border rounded-lg bg-card/50 overflow-hidden shadow-sm">
      <div className="overflow-auto max-h-[400px]">
        <table className="w-full text-sm text-left">
          <thead className="sticky top-0 bg-muted/80 backdrop-blur-sm z-10 border-b">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="px-4 py-3 font-semibold text-foreground/80 tracking-wider">
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-border/50">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-muted/30 transition-colors">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-2 text-foreground/90 whitespace-nowrap">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between px-4 py-2 bg-muted/30 border-t shrink-0">
        <span className="text-xs text-muted-foreground">
          Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()} ({data.length} rows)
        </span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-7 text-xs px-2" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
            Prev
          </Button>
          <Button variant="outline" size="sm" className="h-7 text-xs px-2" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
};

interface Thread {
  id: string;
  query: string;
  status: 'processing' | 'done' | 'error';
  currentStep?: string;
  insight?: string;
  chartConfig?: any;
  tableData?: any[];
  sql?: string;
  graphData?: any; // Semantic Graph Traversal
  error?: string;
}

const generateId = () => Math.random().toString(36).substr(2, 9);

const SUGGESTIONS = [
  "Phân tích theo tháng",
  "Top 5 cao nhất là gì?",
  "So sánh tỷ trọng"
];

const V4Dashboard = () => {
  const { selectedGraph } = useDatabase();
  const { toast } = useToast();
  const { vendor, apiKey, modelName, isApiKeyValid, customEndpoint } = useSettings();
  const [inputValue, setInputValue] = useState('');
  const [threads, setThreads] = useState<Thread[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [threads]);

  const handleSearch = async (queryText?: string) => {
    const textToSearch = typeof queryText === 'string' ? queryText : inputValue;
    if (!textToSearch.trim()) return;
    if (!selectedGraph) {
      toast({
        title: "No Database Selected",
        description: "Please select a database from the sidebar.",
        variant: "destructive",
      });
      return;
    }

    setInputValue(''); 
    
    const threadId = generateId();
    const newThread: Thread = {
      id: threadId,
      query: textToSearch,
      status: 'processing',
      currentStep: 'Khởi tạo phân tích...',
    };
    
    setThreads(prev => [...prev, newThread]);

    try {
      for await (const message of ChatService.streamQuery({
        query: textToSearch,
        database: selectedGraph.id,
        version: 'v4',
        customApiKey: isApiKeyValid ? apiKey : undefined,
        customModel: modelName,
        customVendor: vendor,
        customApiBase: isApiKeyValid ? customEndpoint : undefined,
      })) {
        setThreads(prev => prev.map(t => {
          if (t.id !== threadId) return t;

          let updated = { ...t };
          
          if (message.type === 'status' || message.type === 'reasoning_step') {
            updated.currentStep = message.content || 'Đang xử lý...';
          } else if (message.type === 'reasoning_graph') {
            updated.graphData = message.data;
          } else if (message.type === 'sql_query') {
            updated.sql = message.data;
          } else if (message.type === 'query_result' || message.type === 'result') {
            // In v4, data is the raw array of rows
            if (Array.isArray(message.data)) {
              updated.tableData = message.data;
            }
          } else if (message.type === 'chart_config') {
            updated.chartConfig = message.data;
          } else if (message.type === 'ai_response') {
            updated.insight = message.message || message.content;
            updated.status = 'done';
            updated.currentStep = 'Hoàn tất';
          } else if (message.type === 'error') {
            updated.status = 'error';
            updated.error = message.content || "An error occurred.";
            updated.currentStep = 'Lỗi';
          }
          return updated;
        }));
      }
    } catch (error: any) {
      setThreads(prev => prev.map(t => {
        if (t.id === threadId) {
          return {
            ...t,
            status: 'error',
            error: error.message || "Failed to process query",
            currentStep: 'Lỗi'
          };
        }
        return t;
      }));
    }
  };

  const getGraphOption = (graphData: any) => {
    if (!graphData || !graphData.nodes || graphData.nodes.length === 0) return null;
    
    const echartsNodes = graphData.nodes.map((n: any) => {
      let color = '#94a3b8'; // default
      let size = 30;
      if (n.label === 'Question') { color = '#3b82f6'; size = 40; } // blue
      else if (n.label === 'Table') { color = '#10b981'; size = 35; } // green
      else if (n.label === 'Metric') { color = '#f59e0b'; size = 35; } // yellow
      else if (n.label === 'Dimension') { color = '#8b5cf6'; size = 35; } // purple
      
      return {
        id: n.id,
        name: n.name,
        symbolSize: size,
        itemStyle: { color },
        label: { show: true, position: 'bottom' },
        tooltip: {
          formatter: `<b>${n.label}</b>: ${n.name}<br/>${n.properties?.description || n.properties?.formula || ''}`
        }
      };
    });
    
    const echartsEdges = (graphData.edges || []).map((e: any) => ({
      source: e.source,
      target: e.target,
      label: { show: true, formatter: e.label, fontSize: 10 }
    }));

    return {
      tooltip: {},
      animationDurationUpdate: 1500,
      animationEasingUpdate: 'quinticInOut',
      series: [
        {
          type: 'graph',
          layout: 'force',
          data: echartsNodes,
          links: echartsEdges,
          roam: true,
          label: { position: 'right', formatter: '{b}' },
          lineStyle: { color: 'source', curveness: 0.1, width: 2 },
          force: { repulsion: 300, edgeLength: [50, 150] }
        }
      ]
    };
  };

  const activeProcessing = threads.some(t => t.status === 'processing');

  return (
    <div className="w-full h-full flex flex-col bg-transparent overflow-hidden relative font-sans">

      {/* Main Thread Content Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 md:p-8 scroll-smooth">
        <div className="max-w-5xl mx-auto flex flex-col gap-10 pb-40">
          
          {threads.length === 0 && (
            <div className="flex flex-col items-center justify-center py-32 text-center opacity-90 animate-in fade-in slide-in-from-bottom-8 duration-700">
              <div className="w-24 h-24 bg-gradient-to-tr from-primary/20 to-blue-500/20 text-primary rounded-3xl flex items-center justify-center mb-8 shadow-inner rotate-3">
                <BarChart3 className="w-12 h-12 -rotate-3" />
              </div>
              <h2 className="text-4xl font-extrabold mb-4 tracking-tight">Ask your database</h2>
              <p className="text-muted-foreground max-w-lg text-lg leading-relaxed">
                Experience the power of Graph-RAG. Type your question below to instantly generate insights, charts, and reasoning lineage.
              </p>
            </div>
          )}

          {threads.map((thread) => (
            <div key={thread.id} className="flex flex-col gap-5 animate-in fade-in slide-in-from-bottom-4 duration-500">
              {/* User Question */}
              <div className="flex items-start gap-4 justify-end">
                <div className="pt-2">
                  <div className="bg-[#2563eb] text-white px-6 py-4 rounded-2xl rounded-tr-sm shadow-sm text-sm max-w-[80%] float-right leading-relaxed font-medium">
                    {thread.query}
                  </div>
                </div>
              </div>

              {/* AI Response Block */}
              <div className="flex flex-col gap-3">
                {thread.status === 'processing' && (
                  <div className="flex items-center gap-3 text-sm text-primary/80 bg-primary/5 w-fit px-4 py-2 rounded-full border border-primary/10 shadow-sm animate-pulse">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="font-medium">{thread.currentStep}</span>
                  </div>
                )}
                {thread.status === 'error' && (
                  <div className="p-4 bg-red-50 text-red-600 border border-red-200 rounded-2xl flex items-start gap-3 shadow-sm w-fit">
                    <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                    <span className="font-medium">{thread.error}</span>
                  </div>
                )}

                {(thread.status === 'done' || thread.insight || thread.chartConfig || thread.tableData || thread.graphData) && (
                  <div className="flex flex-col gap-5 p-6 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-xl shadow-gray-200/40 dark:shadow-black/40 rounded-3xl w-full">
                    
                    {/* Insight Text */}
                    {thread.insight && (
                      <div className="text-gray-800 dark:text-gray-200 text-lg leading-relaxed max-w-none border-b border-gray-100 dark:border-gray-800 pb-5">
                        {thread.insight}
                      </div>
                    )}

                    {/* Interactive Tabs */}
                    <Tabs defaultValue={thread.chartConfig ? 'chart' : 'data'} className="w-full">
                      <TabsList className="grid w-full grid-cols-4 max-w-[500px] mb-6 bg-gray-100/80 dark:bg-gray-800/80 p-1 rounded-xl">
                        <TabsTrigger value="chart" disabled={!thread.chartConfig} className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm transition-all">
                          <LayoutDashboard className="w-4 h-4 mr-2" /> Chart
                        </TabsTrigger>
                        <TabsTrigger value="data" disabled={!thread.tableData || thread.tableData.length === 0} className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm transition-all">
                          <TableIcon className="w-4 h-4 mr-2" /> Data
                        </TabsTrigger>
                        <TabsTrigger value="graph" disabled={!thread.graphData} className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm transition-all text-blue-600 data-[state=active]:text-blue-700">
                          <Network className="w-4 h-4 mr-2" /> Graph
                        </TabsTrigger>
                        <TabsTrigger value="sql" disabled={!thread.sql} className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm transition-all text-amber-600 data-[state=active]:text-amber-700">
                          <Code className="w-4 h-4 mr-2" /> SQL
                        </TabsTrigger>
                      </TabsList>
                      
                      <TabsContent value="chart" className="mt-0 outline-none">
                        {thread.chartConfig ? (
                          <div className="w-full min-h-[450px] border border-gray-100 dark:border-gray-800 rounded-2xl bg-gray-50/50 dark:bg-gray-900/50 p-4 shadow-inner">
                            <ReactECharts
                              option={thread.chartConfig}
                              style={{ height: '450px', width: '100%' }}
                              opts={{ renderer: 'svg' }}
                              notMerge={true}
                              lazyUpdate={true}
                            />
                          </div>
                        ) : (
                          <div className="p-10 text-center text-gray-400 border border-dashed rounded-2xl">No chart visualization available.</div>
                        )}
                      </TabsContent>
                      
                      <TabsContent value="data" className="mt-0 outline-none">
                        {thread.tableData && thread.tableData.length > 0 ? (
                          <DataTable data={thread.tableData} />
                        ) : (
                          <div className="p-10 text-center text-gray-400 border border-dashed rounded-2xl">No data available.</div>
                        )}
                      </TabsContent>

                      <TabsContent value="graph" className="mt-0 outline-none">
                        {thread.graphData ? (
                          <div className="w-full min-h-[450px] border border-gray-100 dark:border-gray-800 rounded-2xl bg-gradient-to-br from-gray-50 to-white dark:from-gray-900 dark:to-black p-4 shadow-inner relative overflow-hidden">
                            <div className="absolute top-4 left-4 z-10 bg-white/80 dark:bg-black/80 backdrop-blur-sm p-3 rounded-xl border shadow-sm text-xs space-y-2">
                              <div className="font-semibold text-gray-700 dark:text-gray-300 mb-1">Graph Legend</div>
                              <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#3b82f6]"></span> User Question</div>
                              <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#f59e0b]"></span> Metric</div>
                              <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#8b5cf6]"></span> Dimension</div>
                              <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#10b981]"></span> Table</div>
                            </div>
                            <ReactECharts
                              option={getGraphOption(thread.graphData)}
                              style={{ height: '450px', width: '100%' }}
                              notMerge={true}
                            />
                          </div>
                        ) : (
                          <div className="p-10 text-center text-gray-400 border border-dashed rounded-2xl">No lineage graph available.</div>
                        )}
                      </TabsContent>
                      
                      <TabsContent value="sql" className="mt-0 outline-none">
                        <div className="relative border border-gray-100 dark:border-gray-800 rounded-2xl bg-gray-900 text-gray-100 p-6 font-mono text-sm overflow-x-auto whitespace-pre-wrap shadow-inner">
                          {thread.sql}
                        </div>
                      </TabsContent>
                    </Tabs>
                    
                    {/* Follow-up Suggestions */}
                    {thread.status === 'done' && (
                      <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-gray-100 dark:border-gray-800 mt-2">
                        <span className="text-xs text-gray-400 font-medium mr-2">Gợi ý tiếp theo:</span>
                        {SUGGESTIONS.map((sug, i) => (
                          <button 
                            key={i} 
                            onClick={() => handleSearch(`${thread.query} -> ${sug}`)}
                            className="px-4 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 dark:text-gray-300 dark:bg-gray-800 dark:hover:bg-gray-700 rounded-full transition-colors"
                          >
                            {sug}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Fixed Bottom Input Area */}
      <div className="absolute bottom-0 left-0 right-0 px-4 pb-6 pt-12 bg-gradient-to-t from-transparent via-white/80 to-transparent dark:from-transparent dark:via-black/80 z-20">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={(e) => { e.preventDefault(); handleSearch(); }} className="flex gap-3 relative rounded-[28px] bg-gray-50/80 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 transition-all hover:bg-gray-100/80 focus-within:bg-white focus-within:shadow-md focus-within:border-[#2563eb]/30">
            <div className="relative flex-1 group">
              <div className="absolute inset-y-0 left-6 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-gray-400 group-focus-within:text-[#2563eb] transition-colors" />
              </div>
              <Input
                type="text"
                placeholder="Khám phá dữ liệu của bạn... (VD: Doanh thu theo tháng)"
                className="pl-14 pr-6 py-8 text-[15px] border-0 focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent shadow-none text-gray-700 font-medium"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                disabled={activeProcessing || !selectedGraph}
              />
            </div>
            <div className="p-2 shrink-0 flex items-center pr-3">
              <Button 
                type="submit" 
                disabled={activeProcessing || !inputValue.trim() || !selectedGraph}
                className="h-[46px] w-[46px] p-0 rounded-full bg-[#8ba0ff] hover:bg-[#2563eb] text-white shadow-sm transition-all active:scale-95 disabled:opacity-50"
              >
                {activeProcessing ? (
                  <Loader2 className="w-6 h-6 animate-spin" />
                ) : (
                  <svg className="w-5 h-5 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
                )}
              </Button>
            </div>
          </form>
          <div className="text-center mt-3">
            <span className="text-[10px] uppercase tracking-widest font-bold text-gray-400 flex items-center justify-center gap-1.5">
              <Network className="w-3 h-3" />
              Powered by StrongBI Graph-RAG Engine
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default V4Dashboard;
