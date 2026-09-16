import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDatabase } from '@/contexts/DatabaseContext';
import { useSettings } from '@/contexts/SettingsContext';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';
import { 
  Search, Brain, Table as TableIcon, LayoutDashboard, Loader2, Code, 
  ChevronRight, CheckCircle2, AlertCircle, BarChart3, LineChart, PieChart, 
  Layers, Network, Sparkles, Link as LinkIcon, Download, Pin, Copy, Check, 
  TrendingUp, Image as ImageIcon, FileSpreadsheet, ArrowUpRight
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { 
  cn, 
  sanitizeEChartsFormatter 
} from "@/lib/utils";
import { ChatService } from '@/services/chat';
import { dashboardService } from '@/services/dashboard';
import { TextShimmer } from '@/components/prompt-kit/text-shimmer';
import ReactECharts from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
import { V4QuestionRecommenderModal } from '@/components/v4/V4QuestionRecommenderModal';

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

  const handleExportCSV = () => {
    if (!data || data.length === 0) return;
    const headers = Object.keys(data[0]);
    const csvRows = [
      headers.join(','),
      ...data.map(row => headers.map(header => {
        const cell = row[header] === null || row[header] === undefined ? '' : row[header];
        return `"${String(cell).replace(/"/g, '""')}"`;
      }).join(','))
    ];
    const csvString = csvRows.join('\n');
    const blob = new Blob([new Uint8Array([0xEF, 0xBB, 0xBF]), csvString], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    if (link.download !== undefined) {
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `export_data_${new Date().getTime()}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  if (!data || data.length === 0) return (
    <div className="flex items-center justify-center p-8 text-muted-foreground/50 text-sm border rounded-lg bg-card/50">
      Chưa có dữ liệu để hiển thị.
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
          Trang {table.getState().pagination.pageIndex + 1}/{table.getPageCount()} ({data.length} dòng)
        </span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-7 text-xs px-2 text-green-600 hover:text-green-700 hover:bg-green-50 border-green-200" onClick={handleExportCSV}>
            <Download className="w-3 h-3 mr-1" /> Xuất CSV
          </Button>
          <Button variant="outline" size="sm" className="h-7 text-xs px-2" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
            Trước
          </Button>
          <Button variant="outline" size="sm" className="h-7 text-xs px-2" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
            Sau
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
  steps?: string[];          // các bước đã đi qua — hiển thị timeline trạng thái
  insight?: string;
  chartConfig?: any;
  tableData?: any[];
  sql?: string;
  graphData?: any; // Semantic Graph Traversal
  error?: string;
  metrics?: {
    total_tokens: number;
    cost_usd: number;
    api_calls_count: number;
    engine_version: string;
  };
}

const generateId = () => Math.random().toString(36).substr(2, 9);

const SUGGESTIONS = [
  "Phân tích theo tháng",
  "Top 5 cao nhất là gì?",
  "So sánh tỷ trọng"
];

// Danh mục câu hỏi thông minh giúp người dùng khởi động nhanh và hiệu quả
const PROMPT_CATEGORIES = [
  {
    category: "Doanh thu & Đơn hàng",
    icon: TrendingUp,
    color: "from-blue-500/10 to-indigo-500/10 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-900/50",
    questions: [
      { label: "Doanh thu 30 ngày qua", query: "Doanh thu 30 ngày qua" },
      { label: "Doanh số theo tháng năm nay", query: "Số lượng đơn hàng và doanh số theo tháng năm nay" },
      { label: "Doanh thu theo kênh bán lẻ vs sỉ", query: "Doanh số bán hàng phân bổ theo kênh phân phối" }
    ]
  },
  {
    category: "Khách hàng & Thị trường",
    icon: Sparkles,
    color: "from-emerald-500/10 to-teal-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900/50",
    questions: [
      { label: "Top 10 khách hàng lớn nhất", query: "10 khách hàng mua nhiều nhất tháng này" },
      { label: "Tỷ lệ mua lặp lại của khách", query: "Tỷ lệ khách hàng mua lại và số đơn hàng trung bình" },
      { label: "Khách hàng mới phát sinh đơn", query: "Danh sách khách hàng mới có đơn hàng trong 30 ngày qua" }
    ]
  },
  {
    category: "Sản phẩm & Danh mục",
    icon: BarChart3,
    color: "from-purple-500/10 to-pink-500/10 text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-900/50",
    questions: [
      { label: "Top 10 sản phẩm bán chạy nhất", query: "Top 10 sản phẩm doanh thu cao nhất 30 ngày qua" },
      { label: "Cơ cấu doanh thu theo nhóm hàng", query: "Tỷ trọng doanh thu theo từng ngành hàng hoặc danh mục sản phẩm" },
      { label: "Sản phẩm tăng trưởng nhanh nhất", query: "Top sản phẩm có tốc độ tăng trưởng doanh số nhanh nhất" }
    ]
  }
];

// Rút gọn message bước từ backend ("Bước 2: Phân tích Cấu trúc Đồ thị (Graph Lineage)...")
// thành nhãn ngắn cho timeline trạng thái.
const cleanStep = (s: string) =>
  s.replace(/^\s*Bước\s*\d+\s*:\s*/i, '').replace(/\.{3,}\s*$/, '').trim();

// Chuyển đổi chart type trực tiếp trên giao diện
const transformChartConfig = (rawConfig: any, targetType?: string) => {
  if (!rawConfig) return null;
  // Sanitize bad Python formatting hallucinated by the agent
  let config = sanitizeEChartsFormatter(JSON.parse(JSON.stringify(rawConfig)));
  
  if (!targetType) return config;

  if (!config.series) return config;

  if (targetType === 'line' || targetType === 'area') {
    config.series = (config.series || []).map((s: any) => ({
      ...s,
      type: 'line',
      smooth: true,
      areaStyle: targetType === 'area' ? { opacity: 0.25 } : undefined,
    }));
  } else if (targetType === 'bar') {
    config.series = (config.series || []).map((s: any) => ({
      ...s,
      type: 'bar',
      areaStyle: undefined,
    }));
  } else if (targetType === 'pie') {
    config.xAxis = undefined;
    config.yAxis = undefined;
    config.series = (config.series || []).map((s: any) => ({
      ...s,
      type: 'pie',
      radius: ['40%', '70%'],
    }));
  }
  return config;
};

// Chuông nhẹ khi bắt đầu trả kết quả — Web Audio, không cần file âm thanh.
let _audioCtx: AudioContext | null = null;
const playDing = () => {
  try {
    _audioCtx = _audioCtx || new (window.AudioContext || (window as any).webkitAudioContext)();
    const ctx = _audioCtx;
    if (ctx.state === 'suspended') ctx.resume();
    const t0 = ctx.currentTime;
    [[880, 0], [1318.5, 0.12]].forEach(([freq, delay]) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq as number;
      gain.gain.setValueAtTime(0.0001, t0 + (delay as number));
      gain.gain.exponentialRampToValueAtTime(0.06, t0 + (delay as number) + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + (delay as number) + 0.35);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t0 + (delay as number));
      osc.stop(t0 + (delay as number) + 0.4);
    });
  } catch { /* trình duyệt chặn audio — bỏ qua */ }
};

// Hiệu ứng streaming (typewriter) cho câu trả lời — theo flag features.streaming
const Typewriter = ({ text, enabled }: { text: string; enabled: boolean }) => {
  const [n, setN] = useState(enabled ? 0 : text.length);
  useEffect(() => {
    if (!enabled) { setN(text.length); return; }
    setN(0);
    const iv = setInterval(() => setN(prev => {
      if (prev >= text.length) { clearInterval(iv); return prev; }
      return prev + 14;
    }), 25);
    return () => clearInterval(iv);
  }, [text, enabled]);
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{text.slice(0, n)}</ReactMarkdown>;
};

// Tailwind cần class literal — không dùng template string động
const GRID_COLS: Record<number, string> = {
  1: 'grid-cols-1', 2: 'grid-cols-2', 3: 'grid-cols-3', 4: 'grid-cols-4',
};

const V4Dashboard = () => {
  const navigate = useNavigate();
  const { selectedGraph } = useDatabase();
  const { toast } = useToast();
  const { user } = useAuth();
  const { vendor, apiKey, modelName, isApiKeyValid, customEndpoint } = useSettings();
  const [inputValue, setInputValue] = useState('');
  const [engineVersion, setEngineVersion] = useState<'v4' | 'v4_5' | 'v5'>('v4_5');
  const [threads, setThreads] = useState<Thread[]>([]);
  const [animateId, setAnimateId] = useState<string | null>(null);
  const [chartTypeMap, setChartTypeMap] = useState<Record<string, string>>({});
  const [copiedSqlId, setCopiedSqlId] = useState<string | null>(null);
  const [isRecommenderOpen, setIsRecommenderOpen] = useState(false);
  const chartRefs = useRef<Record<string, any>>({});
  const streamingOn = user?.features && (user.features as any).streaming !== false;
  const scrollRef = useRef<HTMLDivElement>(null);

  // Tabs kết quả theo ui_permissions per-account (fallback: admin thấy hết, còn lại chỉ answer)
  const isAdmin = (user?.role || '').toLowerCase() === 'admin';
  const visibleTabs: string[] =
    user?.ui_permissions?.result_tabs ?? (isAdmin ? ['chart', 'data', 'graph', 'sql'] : []);

  // ── Persist chat theo user + graph: reload không mất hội thoại ──
  const storageKey = user && selectedGraph ? `v4_threads:${user.id}:${selectedGraph.id}` : null;

  useEffect(() => {
    if (!storageKey) return;
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const loaded: Thread[] = JSON.parse(raw).map((t: any) => 
          t.status === 'processing' ? { ...t, status: 'error', error: 'Mất kết nối hoặc quá trình phân tích bị gián đoạn. Vui lòng thử lại.' } : t
        );
        setThreads(loaded);
      } else {
        setThreads([]);
      }
    } catch {
      setThreads([]);
    }
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey || threads.length === 0) return;
    try {
      // Cap: 20 hội thoại gần nhất, mỗi bảng tối đa 200 dòng, bỏ graphData (nặng)
      const slim = threads.slice(-20).map(t => ({
        ...t, graphData: undefined,
        tableData: t.tableData ? t.tableData.slice(0, 200) : undefined,
      }));
      localStorage.setItem(storageKey, JSON.stringify(slim));
    } catch { /* localStorage đầy — bỏ qua, không chặn UI */ }
  }, [threads, storageKey]);

  const handlePinChart = async (thread: Thread) => {
    if (!thread.chartConfig) return;
    try {
      // 1. Get existing dashboards or auto-create a default one
      const dashboards = await dashboardService.getDashboards();
      let targetDashboardId = dashboards[0]?.id;
      
      if (!targetDashboardId) {
        const newDash = await dashboardService.createDashboard("Báo cáo Tổng quan", "Dashboard phân tích mặc định");
        targetDashboardId = newDash.id;
      }
      
      // 2. Add widget into dashboard
      const chartType = thread.chartConfig?.chart_type || thread.chartConfig?.series?.[0]?.type || 'bar';
      await dashboardService.addWidget(targetDashboardId, {
        title: thread.query || "Biểu đồ phân tích",
        graph_id: selectedGraph?.id || "",
        chart_type: String(chartType).toLowerCase(),
        sql_query: thread.sql || "",
        chart_config: thread.chartConfig,
        layout_w: 6,
        layout_h: 4,
      });

      toast({
        title: "Đã lưu vào Dashboard thành công!",
        description: "Biểu đồ đã được thêm vào bảng điều khiển Dashboards.",
      });
    } catch (e: any) {
      console.error("Failed to pin widget:", e);
      toast({
        variant: "destructive",
        title: "Lỗi lưu Dashboard",
        description: e.message || "Không thể thêm biểu đồ vào Dashboard.",
      });
    }
  };

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
        title: "Chưa kết nối dữ liệu",
        description: "Hệ thống đang kết nối — thử lại sau vài giây.",
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
      currentStep: 'Đang phân tích câu hỏi',
    };

    setThreads(prev => [...prev, newThread]);

    // State đầu không được đứng yên quá 2s: backend chưa trả bước nào thì escalate
    // text để user biết hệ thống vẫn đang chạy (câu khó/graph lớn).
    setTimeout(() => {
      setThreads(prev => prev.map(t =>
        t.id === threadId && t.status === 'processing' && !(t.steps && t.steps.length)
          ? { ...t, currentStep: 'Phân tích dữ liệu sâu' }
          : t
      ));
    }, 2000);

    try {
      // Follow-up context: 3 hội thoại hoàn tất gần nhất (câu hỏi + tóm tắt trả lời)
      // Contextual 5 turn gần nhất; digest chỉ giữ cột khoá (id/code/name) + số liệu
      // để đủ 5 dòng trong budget — follow-up bind thực thể bằng PRIMARY KEY.
      const history = threads.filter(t => t.status === 'done').slice(-5).flatMap(t => {
        let digest = '';
        if (t.tableData?.length) {
          const rows = t.tableData.slice(0, 5).map(r => {
            const out: Record<string, any> = {};
            for (const [k, v] of Object.entries(r)) {
              if (/(_id|_code|name|id)$/i.test(k) || typeof v === 'number') out[k] = v;
            }
            return out;
          });
          digest = `\n[DATA lượt này — bind bằng id/code khi hỏi tiếp]: ${JSON.stringify(rows)}`.slice(0, 800);
        }
        return [
          { role: 'user' as const, content: t.query },
          { role: 'assistant' as const, content: ((t.insight || '').slice(0, 300) + digest).slice(0, 1100) },
        ];
      });
      for await (const message of ChatService.streamQuery({
        query: textToSearch,
        database: selectedGraph.id,
        version: engineVersion,
        threadId,
        history,
        customApiKey: isApiKeyValid ? (apiKey || undefined) : undefined,
        // Chỉ override model khi user đã cấu hình API key hợp lệ trong Settings —
        // nếu không, backend dùng LLM server-side (COMPLETION_MODEL trong .env)
        customModel: isApiKeyValid ? (modelName || undefined) : undefined,
        customVendor: isApiKeyValid ? (vendor || undefined) : undefined,
        customApiBase: isApiKeyValid ? (customEndpoint || undefined) : undefined,
      })) {
        setThreads(prev => prev.map(t => {
          if (t.id !== threadId) return t;

          let updated = { ...t };

          if (message.type === 'status' || message.type === 'reasoning_step') {
            const step = cleanStep(message.content || 'Đang đánh giá câu trả lời');
            updated.currentStep = step;
            // Gom timeline, bỏ trùng liên tiếp (backend có thể lặp message)
            const prev = t.steps || [];
            updated.steps = prev[prev.length - 1] === step ? prev : [...prev, step];
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
            setAnimateId(threadId);
            updated.status = 'done';
            updated.currentStep = 'Hoàn tất';
            playDing(); // chuông nhẹ khi bắt đầu trả kết quả
          } else if (message.type === 'metrics') {
            if (message.data) {
              updated.metrics = {
                total_tokens: message.data.total_tokens || 0,
                cost_usd: message.data.cost_usd || 0,
                api_calls_count: message.data.api_calls_count || 0,
                engine_version: message.data.engine_version || engineVersion
              };
            }
          } else if (message.type === 'error') {
            updated.status = 'error';
            updated.error = message.content || "Có lỗi xảy ra khi xử lý câu hỏi.";
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
            error: error.message || "Không xử lý được câu hỏi — thử lại giúp nhé.",
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
            <div className="flex flex-col items-center justify-center py-12 md:py-20 text-center opacity-95 animate-in fade-in slide-in-from-bottom-6 duration-700 px-2 max-w-4xl mx-auto">
              <div className="w-16 h-16 md:w-20 md:h-20 bg-gradient-to-tr from-blue-600/20 via-indigo-500/20 to-purple-500/20 text-blue-600 rounded-3xl flex items-center justify-center mb-6 shadow-inner rotate-3 border border-blue-200/50 dark:border-blue-800/50">
                <BarChart3 className="w-8 h-8 md:w-10 md:h-10 -rotate-3 text-blue-600 dark:text-blue-400" />
              </div>
              <h2 className="text-2xl md:text-4xl font-extrabold mb-2 tracking-tight text-gray-900 dark:text-white">
                Trợ lý Phân tích Dữ liệu Thông minh
              </h2>
              <p className="text-muted-foreground max-w-lg text-sm md:text-base leading-relaxed mb-8">
                Đặt câu hỏi bằng ngôn ngữ tự nhiên để AI tự động truy vấn, phân tích số liệu và dựng biểu đồ trực quan.
              </p>

              {/* Categorized Prompt Starters */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full text-left">
                {PROMPT_CATEGORIES.map((cat, idx) => {
                  const Icon = cat.icon;
                  return (
                    <div 
                      key={idx} 
                      className="p-4 rounded-2xl bg-white/80 dark:bg-gray-900/80 border border-gray-200/80 dark:border-gray-800 backdrop-blur-sm shadow-sm hover:shadow-md transition-all flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center gap-2 mb-3">
                          <div className={cn("p-1.5 rounded-lg border bg-gradient-to-br", cat.color)}>
                            <Icon className="w-4 h-4" />
                          </div>
                          <span className="text-xs font-bold text-gray-800 dark:text-gray-200 uppercase tracking-wide">
                            {cat.category}
                          </span>
                        </div>
                        <div className="space-y-1.5">
                          {cat.questions.map((q, qIdx) => (
                            <button
                              key={qIdx}
                              onClick={() => handleSearch(q.query)}
                              disabled={!selectedGraph}
                              className="w-full text-left p-2 rounded-xl text-xs font-medium text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50/70 dark:hover:bg-blue-950/40 border border-transparent hover:border-blue-100 dark:hover:border-blue-900 transition-all flex items-center justify-between group"
                            >
                              <span className="truncate pr-2">{q.label}</span>
                              <ArrowUpRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 text-blue-600 transition-opacity shrink-0" />
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Question Recommender CTA Button */}
              <div className="mt-6 flex items-center justify-center">
                <Button
                  onClick={() => setIsRecommenderOpen(true)}
                  disabled={!selectedGraph}
                  className="bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-2xl text-xs h-10 px-5 gap-2 shadow-lg shadow-blue-500/20 font-semibold transition-all hover:scale-[1.02] active:scale-[0.98]"
                >
                  <Sparkles className="w-4 h-4" />
                  Khám phá gợi ý câu hỏi phân tích dữ liệu (AI Questions)
                </Button>
              </div>
            </div>
          )}

          {threads.map((thread) => {
            const currentChartType = chartTypeMap[thread.id] || thread.chartConfig?.series?.[0]?.type || 'bar';
            const transformedConfig = transformChartConfig(thread.chartConfig, currentChartType);

            return (
            <div key={thread.id} className="flex flex-col gap-5 animate-in fade-in slide-in-from-bottom-4 duration-500">
              {/* User Question + nút copy link báo lỗi (deep-link cho admin trace) */}
              <div className="flex items-start gap-2 justify-end">
                <button
                  title="Copy link hội thoại này để phản hồi chất lượng"
                  onClick={() => {
                    navigator.clipboard.writeText(`${window.location.origin}/conversations/${thread.id}`);
                    toast({ title: "Đã copy link", description: "Link hội thoại đã được sao chép vào bộ nhớ tạm." });
                  }}
                  className="mt-3 p-2 rounded-lg text-gray-400 hover:text-[#2563eb] hover:bg-blue-50 dark:hover:bg-blue-950 transition-colors shrink-0"
                >
                  <LinkIcon className="w-4 h-4" />
                </button>
                <div className="bg-[#2563eb] text-white px-5 py-3.5 mt-2 rounded-2xl rounded-tr-sm shadow-sm text-sm max-w-[80%] md:max-w-[70%] leading-relaxed font-medium break-words">
                  {thread.query}
                </div>
              </div>

              {/* AI Response Block */}
              <div className="flex flex-col gap-3">
                {thread.status === 'processing' && (
                  <div className="flex flex-col gap-1 w-fit max-w-full px-3.5 py-2 rounded-xl border border-primary/10 bg-primary/5 shadow-sm">
                    {/* Các bước đã qua — mờ dần, có tick */}
                    {(thread.steps || []).slice(0, -1).slice(-3).map((s, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground/70">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500/70 shrink-0" />
                        <span className="truncate">{s}</span>
                      </div>
                    ))}
                    {/* Bước hiện tại */}
                    <div className="flex items-center text-sm">
                      <TextShimmer className="font-medium">{thread.currentStep}</TextShimmer>
                    </div>
                  </div>
                )}
                {thread.status === 'error' && (
                  <div className="p-4 bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900 rounded-2xl flex items-center gap-3 shadow-sm w-fit flex-wrap">
                    <AlertCircle className="w-5 h-5 shrink-0" />
                    <span className="font-medium">{thread.error}</span>
                    <button
                      onClick={() => {
                        // Bỏ thread lỗi khỏi lịch sử rồi hỏi lại đúng câu đó
                        setThreads(prev => prev.filter(x => x.id !== thread.id));
                        handleSearch(thread.query);
                      }}
                      disabled={activeProcessing || !selectedGraph}
                      className="px-3 py-1.5 text-xs font-semibold text-red-600 dark:text-red-300 bg-white dark:bg-transparent border border-red-300 dark:border-red-700 hover:bg-red-100 dark:hover:bg-red-900/40 rounded-full transition-colors shrink-0 disabled:opacity-50"
                    >
                      ↻ Hỏi lại
                    </button>
                  </div>
                )}

                {(thread.status === 'done' || thread.insight || thread.chartConfig || thread.tableData || thread.graphData) && (
                  <div className="flex flex-col gap-5 p-6 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-xl shadow-gray-200/40 dark:shadow-black/40 rounded-3xl w-full">

                    {/* Executive Insight Report */}
                    {thread.insight && (
                      <div className="flex flex-col gap-3.5 border-b border-gray-100 dark:border-gray-800/90 pb-6">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-[11px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest">
                            <span className="w-2 h-2 rounded-full bg-blue-600 dark:bg-blue-400 inline-block"></span>
                            Báo cáo Phân tích Điều hành
                          </div>
                        </div>

                        <div className="text-gray-800 dark:text-gray-200 text-sm md:text-[15px] leading-relaxed max-w-none [&_h1]:text-base [&_h2]:text-[15px] [&_h3]:text-sm [&_h1]:font-bold [&_h2]:font-bold [&_h3]:font-bold [&_h1]:text-gray-900 dark:[&_h1]:text-white [&_h2]:text-gray-900 dark:[&_h2]:text-white [&_h3]:text-gray-900 dark:[&_h3]:text-white [&_h1]:mt-4 [&_h2]:mt-3.5 [&_h3]:mt-3 [&_p]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-1.5 [&_strong]:font-semibold [&_strong]:text-gray-900 dark:[&_strong]:text-white">
                          <Typewriter text={thread.insight} enabled={!!streamingOn && thread.id === animateId} />
                        </div>

                        {thread.metrics && (
                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground select-none">
                            <div className="flex items-center gap-1.5 bg-muted/30 px-2.5 py-1 rounded-md border border-border/50">
                              <span className="font-medium">Model:</span>
                              <span className="text-primary font-semibold uppercase">{thread.metrics.engine_version}</span>
                            </div>
                            <div className="flex items-center gap-1.5 bg-muted/30 px-2.5 py-1 rounded-md border border-border/50">
                              <span className="font-medium">API Calls:</span>
                              <span>{thread.metrics.api_calls_count}</span>
                            </div>
                            <div className="flex items-center gap-1.5 bg-muted/30 px-2.5 py-1 rounded-md border border-border/50">
                              <span className="font-medium">Tokens:</span>
                              <span>{thread.metrics.total_tokens.toLocaleString()}</span>
                            </div>
                            <div className="flex items-center gap-1.5 bg-muted/30 px-2.5 py-1 rounded-md border border-border/50">
                              <span className="font-medium">Cost:</span>
                              <span className="text-emerald-500/90 font-medium">${thread.metrics.cost_usd.toFixed(4)}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Interactive Tabs — theo ui_permissions.result_tabs (admin cấu hình
                        per-account); server cũng đã lọc event nên đây chỉ là lớp UI */}
                    {visibleTabs.length > 0 && (
                      <Tabs defaultValue={visibleTabs.includes('chart') && thread.chartConfig ? 'chart' : visibleTabs[0]} className="w-full">
                        <TabsList className={`grid w-full ${GRID_COLS[visibleTabs.length] || 'grid-cols-4'} max-w-[500px] mb-6 bg-gray-100/80 dark:bg-gray-800/80 p-1 rounded-xl`}>
                          {visibleTabs.includes('chart') && (
                            <TabsTrigger value="chart" disabled={!thread.chartConfig} className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm transition-all">
                              <LayoutDashboard className="w-4 h-4 mr-2" /> Biểu đồ
                            </TabsTrigger>
                          )}
                          {visibleTabs.includes('data') && (
                            <TabsTrigger value="data" disabled={!thread.tableData || thread.tableData.length === 0} className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm transition-all">
                              <TableIcon className="w-4 h-4 mr-2" /> Dữ liệu
                            </TabsTrigger>
                          )}
                          {visibleTabs.includes('graph') && (
                            <TabsTrigger value="graph" disabled={!thread.graphData} className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm transition-all text-blue-600 data-[state=active]:text-blue-700">
                              <Network className="w-4 h-4 mr-2" /> Graph
                            </TabsTrigger>
                          )}
                          {visibleTabs.includes('sql') && (
                            <TabsTrigger value="sql" disabled={!thread.sql} className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm transition-all text-amber-600 data-[state=active]:text-amber-700">
                              <Code className="w-4 h-4 mr-2" /> SQL
                            </TabsTrigger>
                          )}
                        </TabsList>

                        <TabsContent value="chart" className="mt-0 outline-none">
                          {thread.chartConfig ? (
                            <div className="w-full relative min-h-[460px] border border-gray-100 dark:border-gray-800 rounded-2xl bg-gray-50/50 dark:bg-gray-900/50 p-4 shadow-inner flex flex-col">
                              {/* Chart Top Toolbar */}
                              <div className="flex flex-wrap items-center justify-between gap-2 mb-3 pb-2 border-b border-gray-200/50 dark:border-gray-800/50">
                                {/* Chart Type Selector Buttons */}
                                <div className="flex items-center gap-1 bg-white/90 dark:bg-gray-800/90 p-1 rounded-xl border border-gray-200/80 dark:border-gray-700">
                                  {[
                                    { type: 'bar', label: 'Cột', icon: BarChart3 },
                                    { type: 'line', label: 'Đường', icon: LineChart },
                                    { type: 'area', label: 'Miền', icon: Layers },
                                    { type: 'pie', label: 'Tròn', icon: PieChart },
                                  ].map((c) => {
                                    const Icon = c.icon;
                                    const active = currentChartType === c.type;
                                    return (
                                      <button
                                        key={c.type}
                                        type="button"
                                        onClick={() => setChartTypeMap(prev => ({ ...prev, [thread.id]: c.type }))}
                                        className={cn(
                                          "flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-all",
                                          active 
                                            ? "bg-blue-600 text-white shadow-sm" 
                                            : "text-gray-600 dark:text-gray-400 hover:text-gray-900 hover:bg-gray-100 dark:hover:bg-gray-700"
                                        )}
                                      >
                                        <Icon className="w-3.5 h-3.5" />
                                        <span>{c.label}</span>
                                      </button>
                                    );
                                  })}
                                </div>

                                {/* Actions */}
                                <div className="flex items-center gap-1.5">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    className="text-xs h-7 px-2.5 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700"
                                    onClick={() => {
                                      const inst = chartRefs.current[thread.id]?.getEchartsInstance?.();
                                      if (inst) {
                                        const url = inst.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = `chart_${Date.now()}.png`;
                                        a.click();
                                        toast({ title: "Đã tải hình ảnh", description: "Biểu đồ đã được lưu dưới dạng ảnh PNG." });
                                      }
                                    }}
                                  >
                                    <ImageIcon className="w-3.5 h-3.5 mr-1 text-gray-500" /> Tải ảnh
                                  </Button>
                                  <Button
                                    size="sm"
                                    className="text-xs h-7 px-3 bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                                    onClick={() => handlePinChart(thread)}
                                  >
                                    <Pin className="w-3.5 h-3.5 mr-1" /> Ghim vào Dashboard
                                  </Button>
                                </div>
                              </div>

                              <div className="flex-1 w-full min-h-[380px]">
                                <ReactECharts
                                  ref={(e) => { if (e) chartRefs.current[thread.id] = e; }}
                                  option={transformedConfig}
                                  style={{ height: '400px', width: '100%' }}
                                  opts={{ renderer: 'svg' }}
                                  notMerge={true}
                                  lazyUpdate={true}
                                />
                              </div>
                            </div>
                          ) : (
                            <div className="p-10 text-center text-gray-400 border border-dashed rounded-2xl">Câu này không có biểu đồ.</div>
                          )}
                        </TabsContent>

                        <TabsContent value="data" className="mt-0 outline-none">
                          {thread.tableData && thread.tableData.length > 0 ? (
                            <DataTable data={thread.tableData} />
                          ) : (
                            <div className="p-10 text-center text-gray-400 border border-dashed rounded-2xl">Câu này không có bảng dữ liệu.</div>
                          )}
                        </TabsContent>

                        <TabsContent value="graph" className="mt-0 outline-none">
                          {thread.graphData ? (
                            <div className="w-full min-h-[450px] border border-gray-100 dark:border-gray-800 rounded-2xl bg-gradient-to-br from-gray-50 to-white dark:from-gray-900 dark:to-black p-4 shadow-inner relative overflow-hidden">
                              <div className="absolute top-4 left-4 z-10 bg-white/80 dark:bg-black/80 backdrop-blur-sm p-3 rounded-xl border shadow-sm text-xs space-y-2">
                                <div className="font-semibold text-gray-700 dark:text-gray-300 mb-1">Chú giải</div>
                                <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#3b82f6]"></span> Câu hỏi</div>
                                <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#f59e0b]"></span> Metric</div>
                                <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#8b5cf6]"></span> Dimension</div>
                                <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#10b981]"></span> Bảng dữ liệu</div>
                              </div>
                              <ReactECharts
                                option={getGraphOption(thread.graphData)}
                                style={{ height: '450px', width: '100%' }}
                                notMerge={true}
                              />
                            </div>
                          ) : (
                            <div className="p-10 text-center text-gray-400 border border-dashed rounded-2xl">Câu này không có sơ đồ suy luận.</div>
                          )}
                        </TabsContent>

                        <TabsContent value="sql" className="mt-0 outline-none">
                          <div className="relative border border-gray-800 rounded-2xl bg-gray-950 text-gray-100 p-6 font-mono text-sm overflow-x-auto whitespace-pre-wrap shadow-inner">
                            <div className="absolute top-3 right-3">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs bg-gray-800 hover:bg-gray-700 text-gray-200"
                                onClick={() => {
                                  if (thread.sql) {
                                    navigator.clipboard.writeText(thread.sql);
                                    setCopiedSqlId(thread.id);
                                    setTimeout(() => setCopiedSqlId(null), 2000);
                                    toast({ title: "Đã copy SQL", description: "Câu lệnh SQL đã được lưu vào bộ nhớ tạm." });
                                  }
                                }}
                              >
                                {copiedSqlId === thread.id ? (
                                  <>
                                    <Check className="w-3.5 h-3.5 mr-1 text-green-400" /> Đã sao chép
                                  </>
                                ) : (
                                  <>
                                    <Copy className="w-3.5 h-3.5 mr-1" /> Sao chép SQL
                                  </>
                                )}
                              </Button>
                            </div>
                            <pre>{thread.sql}</pre>
                          </div>
                        </TabsContent>
                      </Tabs>
                    )}

                    {/* Follow-up Suggestions */}
                    {thread.status === 'done' && user?.features?.suggestions !== false && (
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
            );
          })}
        </div>
      </div>

      {/* Fixed Bottom Input Area */}
      <div className="absolute bottom-0 left-0 right-0 px-4 pb-6 pt-12 bg-gradient-to-t from-white via-white/95 to-transparent dark:from-[#0c0c0e] dark:via-[#0c0c0e]/95 dark:to-transparent z-20">
        <div className="max-w-4xl mx-auto">
          <div className="flex justify-between items-center mb-2 w-full px-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsRecommenderOpen(true)}
              disabled={!selectedGraph}
              className="rounded-full text-xs h-7 px-3 gap-1.5 border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 bg-white/90 dark:bg-gray-900/90 shadow-sm hover:bg-blue-50 dark:hover:bg-blue-950/40"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Gợi ý câu hỏi phân tích AI
            </Button>
            {threads.length > 0 && !activeProcessing && (
              <button
                type="button"
                title="Xoá lịch sử hiện tại — context follow-up sẽ bắt đầu lại"
                onClick={() => {
                  setThreads([]);
                  setAnimateId(null);
                  if (storageKey) localStorage.removeItem(storageKey);
                }}
                className="px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-700 bg-white/90 dark:bg-gray-900/90 text-xs font-medium text-gray-500 hover:text-red-500 hover:border-red-300 transition-colors shadow-sm"
              >
                + Hội thoại mới
              </button>
            )}
          </div>
          <form onSubmit={(e) => { e.preventDefault(); handleSearch(); }} className="flex gap-3 relative rounded-[28px] bg-gray-50/80 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 transition-all hover:bg-gray-100/80 focus-within:bg-white focus-within:shadow-md focus-within:border-[#2563eb]/30">
            <div className="relative flex-1 group">
              <div className="absolute inset-y-0 left-6 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-gray-400 group-focus-within:text-[#2563eb] transition-colors" />
              </div>
              <Input
                type="text"
                placeholder="Hỏi về doanh thu, đơn hàng, cửa hàng... (VD: Doanh thu theo tháng)"
                className="pl-14 pr-6 py-8 text-[15px] border-0 focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent shadow-none text-gray-700 font-medium"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                disabled={activeProcessing || !selectedGraph}
              />
            </div>

            <div className="p-2 shrink-0 flex items-center pr-3">
              <Popover>
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    disabled={activeProcessing}
                    className="mr-3 flex items-center gap-1.5 bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors outline-none disabled:opacity-50"
                  >
                    <span>{engineVersion === 'v4_5' ? 'Model V4.5 (Dual-Agent)' : engineVersion === 'v4' ? 'Model V4 (Flash)' : 'Model V5 (Deep)'}</span>
                    <svg className="w-3 h-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" /></svg>
                  </button>
                </PopoverTrigger>
                <PopoverContent className="w-[340px] p-2 rounded-2xl mb-2 ml-12 shadow-xl border border-gray-200 dark:border-gray-800" side="top" align="end" sideOffset={10}>
                  <div className="flex flex-col gap-1">
                    <div className="px-2 py-2 mb-1 border-b border-gray-100 dark:border-gray-800">
                      <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Chọn phiên bản phân tích</p>
                    </div>

                    <button
                      type="button"
                      onClick={() => setEngineVersion('v4_5')}
                      className={cn(
                        "flex flex-col items-start gap-1 p-3 rounded-xl text-left transition-colors w-full",
                        engineVersion === 'v4_5' ? "bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-900/30" : "hover:bg-gray-50 dark:hover:bg-gray-800 border border-transparent"
                      )}
                    >
                      <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-2">
                          <span className={cn("font-bold text-sm", engineVersion === 'v4_5' ? "text-blue-700 dark:text-blue-400" : "text-gray-700 dark:text-gray-300")}>Model V4.5 (Dual-Agent Pro)</span>
                          <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-blue-600 text-white">Khuyên dùng</span>
                        </div>
                        {engineVersion === 'v4_5' && <CheckCircle2 className="w-4 h-4 text-blue-600" />}
                      </div>
                      <span className="text-xs text-gray-500 leading-relaxed mt-1">Tách riêng 2 Agent chuyên biệt: Chuyên gia Phân tích Chiến lược (Insight sâu McKinsey) & Chuyên gia Đồ họa ECharts chạy song song.</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setEngineVersion('v4')}
                      className={cn(
                        "flex flex-col items-start gap-1 p-3 rounded-xl text-left transition-colors w-full",
                        engineVersion === 'v4' ? "bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-900/30" : "hover:bg-gray-50 dark:hover:bg-gray-800 border border-transparent"
                      )}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className={cn("font-bold text-sm", engineVersion === 'v4' ? "text-blue-700 dark:text-blue-400" : "text-gray-700 dark:text-gray-300")}>Model V4 (Flash)</span>
                        {engineVersion === 'v4' && <CheckCircle2 className="w-4 h-4 text-blue-600" />}
                      </div>
                      <span className="text-xs text-gray-500 leading-relaxed mt-1">Phiên bản tối ưu tốc độ nhanh. Gộp chung phân tích và vẽ biểu đồ.</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setEngineVersion('v5')}
                      className={cn(
                        "flex flex-col items-start gap-1 p-3 rounded-xl text-left transition-colors w-full",
                        engineVersion === 'v5' ? "bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-900/30" : "hover:bg-gray-50 dark:hover:bg-gray-800 border border-transparent"
                      )}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className={cn("font-bold text-sm", engineVersion === 'v5' ? "text-blue-700 dark:text-blue-400" : "text-gray-700 dark:text-gray-300")}>Model V5 (Deep Graph-RAG)</span>
                        {engineVersion === 'v5' && <CheckCircle2 className="w-4 h-4 text-blue-600" />}
                      </div>
                      <span className="text-xs text-gray-500 leading-relaxed mt-1">Phiên bản phân tích ngữ nghĩa đồ thị đa bước chuyên sâu.</span>
                    </button>
                  </div>
                </PopoverContent>
              </Popover>

              <Button
                type="submit"
                disabled={activeProcessing || !inputValue.trim() || !selectedGraph}
                className="h-[46px] w-[46px] p-0 rounded-full bg-[#8ba0ff] hover:bg-[#2563eb] text-white shadow-sm transition-all active:scale-95 disabled:opacity-50 shrink-0"
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
              Powered by Graph-RAG Engine
            </span>
          </div>
        </div>
      </div>

      {/* Question Recommender Modal */}
      <V4QuestionRecommenderModal
        open={isRecommenderOpen}
        onOpenChange={setIsRecommenderOpen}
        graphId={selectedGraph?.id || ''}
        graphName={selectedGraph?.name}
        onSelectQuestion={(q) => handleSearch(q)}
      />
    </div>
  );
};

export default V4Dashboard;
