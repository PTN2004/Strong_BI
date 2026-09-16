import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Responsive, useContainerWidth } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { useDatabase } from '@/contexts/DatabaseContext';
import { dashboardService } from '@/services/dashboard';
import { Dashboard, DashboardWidget } from '@/types/api';
import ReactECharts from 'echarts-for-react';
import { 
  Plus, LayoutDashboard, Trash2, Loader2, BarChart2, LineChart, 
  PieChart, Maximize2, Download, RefreshCw, 
  Sparkles, Layers, Search, Code, Eye, Check, 
  Printer, TrendingUp, ArrowUpRight, Copy, Database, CheckCircle2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from '@/components/ui/use-toast';
import { useNavigate } from 'react-router-dom';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

const V4Dashboards = () => {
  const navigate = useNavigate();
  const { activeWorkspace } = useWorkspace();
  const { selectedGraph } = useDatabase();
  const { width, containerRef, mounted } = useContainerWidth();
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [activeDashboard, setActiveDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSeeding, setIsSeeding] = useState(false);

  // Widget custom chart type overrides (client-side interactive switching)
  const [chartTypeOverrides, setChartTypeOverrides] = useState<Record<string, string>>({});

  // Fullscreen modal widget
  const [selectedWidget, setSelectedWidget] = useState<DashboardWidget | null>(null);
  const [modalTab, setModalTab] = useState<'chart' | 'sql'>('chart');
  const [copiedSql, setCopiedSql] = useState(false);

  // Chart ref storage for high-res PNG export
  const widgetChartRefs = useRef<Record<string, any>>({});

  // New dashboard creation form state
  const [isCreating, setIsCreating] = useState(false);
  const [newDashName, setNewDashName] = useState('');
  const [newDashDesc, setNewDashDesc] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (activeWorkspace) {
      loadDashboards();
    }
  }, [activeWorkspace?.id]);

  const loadDashboards = async () => {
    try {
      setLoading(true);
      const data = await dashboardService.getDashboards();
      setDashboards(data);
      if (data.length > 0) {
        const targetId = activeDashboard && data.some(d => d.id === activeDashboard.id) 
          ? activeDashboard.id 
          : data[0].id;
        const detail = await dashboardService.getDashboard(targetId);
        setActiveDashboard(detail);
      } else {
        setActiveDashboard(null);
      }
    } catch (error) {
      toast({ title: 'Lỗi', description: 'Không thể tải danh sách Dashboard', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDashboardSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDashName.trim()) {
      toast({ variant: 'destructive', title: 'Lỗi', description: 'Vui lòng nhập tên Dashboard' });
      return;
    }
    try {
      setIsSubmitting(true);
      const created = await dashboardService.createDashboard(newDashName.trim(), newDashDesc.trim() || undefined);
      setNewDashName('');
      setNewDashDesc('');
      setIsCreating(false);
      await loadDashboards();
      const detail = await dashboardService.getDashboard(created.id);
      setActiveDashboard(detail);
      toast({ title: 'Thành công', description: 'Đã tạo Dashboard mới.' });
    } catch (error: any) {
      toast({ title: 'Lỗi', description: error.message || 'Tạo dashboard thất bại', variant: 'destructive' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteDashboard = async (id: string) => {
    if (!confirm("Bạn có chắc muốn xóa Dashboard này?")) return;
    try {
      await dashboardService.deleteDashboard(id);
      toast({ title: 'Thành công', description: 'Đã xóa Dashboard' });
      await loadDashboards();
    } catch (error: any) {
      toast({ title: 'Lỗi', description: error.message || 'Xóa dashboard thất bại', variant: 'destructive' });
    }
  };

  const handleLayoutChange = async (layout: readonly any[]) => {
    if (!activeDashboard) return;
    try {
      // Filter to only widgets that still exist in state to avoid updating deleted widgets
      const currentWidgetIds = new Set(activeDashboard.widgets.map(w => w.id));
      const validLayout = layout.filter(l => currentWidgetIds.has(l.i));
      if (validLayout.length === 0) return;

      const promises = validLayout.map(l => 
        dashboardService.updateWidget(activeDashboard.id, l.i, {
          layout_x: l.x,
          layout_y: l.y,
          layout_w: l.w,
          layout_h: l.h
        })
      );
      await Promise.all(promises);
      
      setActiveDashboard(prev => {
        if (!prev) return prev;
        const newWidgets = prev.widgets.map(w => {
          const newLayout = validLayout.find(l => l.i === w.id);
          if (newLayout) {
            return { ...w, layout: { x: newLayout.x, y: newLayout.y, w: newLayout.w, h: newLayout.h } };
          }
          return w;
        });
        return { ...prev, widgets: newWidgets };
      });
    } catch (error) {
      console.error("Failed to update layout", error);
    }
  };

  const handleDeleteWidget = async (widgetId: string) => {
    if (!activeDashboard) return;
    if (!confirm("Bạn có chắc muốn xóa biểu đồ này khỏi dashboard?")) return;
    
    // Optimistic update first to prevent layout change handler from trying to update a deleted widget
    setActiveDashboard(prev => prev ? {
      ...prev,
      widgets: prev.widgets.filter(w => w.id !== widgetId)
    } : null);

    try {
      await dashboardService.deleteWidget(activeDashboard.id, widgetId);
      toast({ title: 'Thành công', description: 'Đã xóa biểu đồ khỏi Dashboard.' });
    } catch (error: any) {
      // Rollback on failure by reloading from server
      toast({ title: 'Lỗi', description: error.message || 'Xóa biểu đồ thất bại', variant: 'destructive' });
      const detail = await dashboardService.getDashboard(activeDashboard.id).catch(() => null);
      if (detail) setActiveDashboard(detail);
    }
  };

  // Convert chart option to another chart type on-the-fly
  const getTransformedOption = (widget: DashboardWidget, targetType?: string) => {
    const type = targetType || chartTypeOverrides[widget.id] || widget.chart_type || 'bar';
    const config = widget.chart_config ? JSON.parse(JSON.stringify(widget.chart_config)) : {};
    
    if (!config || !config.series) return config;

    if (type === 'line' || type === 'area') {
      config.series = (config.series || []).map((s: any) => ({
        ...s,
        type: 'line',
        smooth: true,
        areaStyle: type === 'area' ? { opacity: 0.25 } : undefined,
      }));
    } else if (type === 'bar') {
      config.series = (config.series || []).map((s: any) => ({
        ...s,
        type: 'bar',
        areaStyle: undefined,
      }));
    } else if (type === 'pie') {
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

  // Export widget chart to PNG
  const handleExportWidgetPNG = (widget: DashboardWidget) => {
    const inst = widgetChartRefs.current[widget.id]?.getEchartsInstance?.();
    if (inst) {
      const url = inst.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
      const a = document.createElement('a');
      a.href = url;
      a.download = `${widget.title.replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1E00-\u1EFF]/g, '_')}_${Date.now()}.png`;
      a.click();
      toast({ title: "Đã xuất hình ảnh", description: `Biểu đồ "${widget.title}" đã được tải về dưới dạng PNG.` });
    }
  };

  // Export widget data to CSV
  const handleExportWidgetCSV = (widget: DashboardWidget) => {
    const config = widget.chart_config;
    if (!config || !config.series) {
      toast({ title: "Thông báo", description: "Không có dữ liệu chuỗi để xuất CSV." });
      return;
    }

    const xAxisData = config.xAxis?.data || [];
    const series = config.series || [];

    let csvContent = "";
    if (xAxisData.length > 0) {
      const headers = ["Danh mục / Thời gian", ...series.map((s: any) => s.name || "Giá trị")];
      const rows = xAxisData.map((label: string, idx: number) => {
        const vals = series.map((s: any) => s.data?.[idx] ?? "");
        return [label, ...vals].map(v => `"${String(v).replace(/"/g, '""')}"`).join(",");
      });
      csvContent = [headers.join(","), ...rows].join("\n");
    } else if (series[0]?.type === 'pie' && series[0]?.data) {
      const headers = ["Hạng mục", "Giá trị"];
      const rows = series[0].data.map((item: any) => `"${item.name || ''}","${item.value || 0}"`);
      csvContent = [headers.join(","), ...rows].join("\n");
    } else {
      csvContent = "Không có cấu trúc bảng phù hợp";
    }

    const blob = new Blob([new Uint8Array([0xEF, 0xBB, 0xBF]), csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${widget.title.replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1E00-\u1EFF]/g, '_')}.csv`;
    link.click();
    toast({ title: "Đã xuất CSV", description: `Dữ liệu biểu đồ "${widget.title}" đã được xuất thành công.` });
  };

  // Seed Starter Executive KPI Pack
  const handleSeedStarterPack = async () => {
    if (!activeDashboard) return;
    try {
      setIsSeeding(true);
      const starterWidgets = [
        {
          title: "Doanh thu 12 tháng qua (Triệu VNĐ)",
          chart_type: "bar",
          layout_w: 6,
          layout_h: 4,
          sql_query: "SELECT strftime('%Y-%m', order_date) as month, SUM(total_amount)/1000000 as revenue FROM orders GROUP BY month ORDER BY month LIMIT 12;",
          chart_config: {
            title: { text: "Doanh thu theo tháng", left: "center", textStyle: { fontSize: 12, fontWeight: 600 } },
            tooltip: { trigger: "axis" },
            grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
            xAxis: { type: "category", data: ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12"] },
            yAxis: { type: "value", name: "Triệu VNĐ" },
            series: [{ name: "Doanh thu", type: "bar", data: [120, 145, 180, 210, 260, 240, 290, 310, 350, 380, 420, 460], itemStyle: { color: "#2563eb", borderRadius: [4, 4, 0, 0] } }]
          }
        },
        {
          title: "Cơ cấu doanh số theo danh mục",
          chart_type: "pie",
          layout_w: 6,
          layout_h: 4,
          sql_query: "SELECT category_name, SUM(amount) as sales FROM order_items JOIN products ON order_items.product_id = products.id GROUP BY category_name;",
          chart_config: {
            title: { text: "Cơ cấu nhóm hàng", left: "center", textStyle: { fontSize: 12, fontWeight: 600 } },
            tooltip: { trigger: "item", formatter: "{b}: {c} tr ({d}%)" },
            legend: { bottom: 0, icon: "circle", textStyle: { fontSize: 10 } },
            series: [{
              name: "Danh mục",
              type: "pie",
              radius: ["38%", "68%"],
              data: [
                { value: 450, name: "Thiết bị điện tử", itemStyle: { color: "#2563eb" } },
                { value: 320, name: "Thời trang & Phụ kiện", itemStyle: { color: "#10b981" } },
                { value: 210, name: "Gia dụng & Đời sống", itemStyle: { color: "#f59e0b" } },
                { value: 160, name: "Thực phẩm & Tiêu dùng", itemStyle: { color: "#8b5cf6" } },
              ]
            }]
          }
        },
        {
          title: "Xu hướng đơn hàng theo tuần",
          chart_type: "area",
          layout_w: 6,
          layout_h: 4,
          sql_query: "SELECT strftime('%W', date) as week, COUNT(id) as total_orders FROM orders GROUP BY week ORDER BY week DESC LIMIT 8;",
          chart_config: {
            title: { text: "Số lượng đơn hàng", left: "center", textStyle: { fontSize: 12, fontWeight: 600 } },
            tooltip: { trigger: "axis" },
            grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
            xAxis: { type: "category", data: ["Tuần 1", "Tuần 2", "Tuần 3", "Tuần 4", "Tuần 5", "Tuần 6", "Tuần 7", "Tuần 8"] },
            yAxis: { type: "value" },
            series: [{ name: "Đơn hàng", type: "line", smooth: true, data: [280, 320, 410, 390, 450, 490, 520, 580], areaStyle: { opacity: 0.2, color: "#10b981" }, itemStyle: { color: "#10b981" } }]
          }
        },
        {
          title: "Top 5 Sản phẩm bán chạy nhất",
          chart_type: "bar",
          layout_w: 6,
          layout_h: 4,
          sql_query: "SELECT product_name, SUM(quantity) as qty FROM order_items GROUP BY product_name ORDER BY qty DESC LIMIT 5;",
          chart_config: {
            title: { text: "Top sản phẩm", left: "center", textStyle: { fontSize: 12, fontWeight: 600 } },
            tooltip: { trigger: "axis" },
            grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
            xAxis: { type: "value" },
            yAxis: { type: "category", data: ["Loa Bluetooth", "Tai nghe TrueWireless", "Bàn phím cơ", "Đồng hồ thông minh", "Chuột không dây"] },
            series: [{ name: "Số lượng bán", type: "bar", data: [150, 230, 310, 420, 560], itemStyle: { color: "#8b5cf6", borderRadius: [0, 4, 4, 0] } }]
          }
        }
      ];

      for (const w of starterWidgets) {
        await dashboardService.addWidget(activeDashboard.id, {
          title: w.title,
          graph_id: selectedGraph?.id || "",
          chart_type: w.chart_type,
          sql_query: w.sql_query,
          chart_config: w.chart_config,
          layout_w: w.layout_w,
          layout_h: w.layout_h
        });
      }

      const detail = await dashboardService.getDashboard(activeDashboard.id);
      setActiveDashboard(detail);
      toast({ title: "Đã nạp bộ chỉ số mẫu", description: "4 biểu đồ phân tích mẫu đã được thêm vào Dashboard thành công." });
    } catch (e: any) {
      toast({ title: "Lỗi", description: e.message || "Không thể nạp dữ liệu mẫu", variant: "destructive" });
    } finally {
      setIsSeeding(false);
    }
  };

  // Filter widgets by search query
  const filteredWidgets = useMemo(() => {
    if (!activeDashboard?.widgets) return [];
    if (!searchQuery.trim()) return activeDashboard.widgets;
    const q = searchQuery.toLowerCase();
    return activeDashboard.widgets.filter(w => 
      w.title.toLowerCase().includes(q) || (w.sql_query && w.sql_query.toLowerCase().includes(q))
    );
  }, [activeDashboard?.widgets, searchQuery]);

  const renderWidget = (widget: DashboardWidget) => {
    const currentType = chartTypeOverrides[widget.id] || widget.chart_type || 'bar';
    const option = getTransformedOption(widget, currentType);

    return (
      <div key={widget.id} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-4 flex flex-col h-full shadow-sm hover:shadow-md transition-all group relative overflow-hidden">
        {/* Widget Header */}
        <div className="flex items-center justify-between mb-2 select-none border-b border-gray-100 dark:border-gray-800 pb-2">
          <div className="flex items-center gap-2 truncate pr-2 drag-handle cursor-move flex-1">
            <BarChart2 className="w-4 h-4 text-blue-600 flex-shrink-0" />
            <span className="truncate text-xs font-semibold text-gray-800 dark:text-gray-100" title={widget.title}>
              {widget.title}
            </span>
          </div>

          {/* Action Toolbar */}
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {/* Chart Type Selector Popover */}
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" className="h-6 w-6 rounded-md text-gray-500 hover:text-blue-600" title="Đổi kiểu biểu đồ">
                  {currentType === 'line' ? <LineChart className="w-3.5 h-3.5" /> :
                   currentType === 'area' ? <Layers className="w-3.5 h-3.5" /> :
                   currentType === 'pie' ? <PieChart className="w-3.5 h-3.5" /> :
                   <BarChart2 className="w-3.5 h-3.5" />}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-36 p-1 rounded-xl shadow-lg border border-gray-200 dark:border-gray-800" align="end">
                <div className="px-2 py-1 text-[10px] font-bold text-gray-400 uppercase">Loại biểu đồ</div>
                {[
                  { id: 'bar', label: 'Cột (Bar)' },
                  { id: 'line', label: 'Đường (Line)' },
                  { id: 'area', label: 'Miền (Area)' },
                  { id: 'pie', label: 'Tròn (Pie)' }
                ].map(t => (
                  <Button
                    key={t.id}
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start text-xs h-7 rounded-lg"
                    onClick={() => setChartTypeOverrides(prev => ({ ...prev, [widget.id]: t.id }))}
                  >
                    <span>{t.label}</span>
                    {currentType === t.id && <Check className="w-3.5 h-3.5 ml-auto text-blue-600" />}
                  </Button>
                ))}
              </PopoverContent>
            </Popover>

            {/* Export PNG */}
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 rounded-md text-gray-500 hover:text-blue-600"
              onClick={() => handleExportWidgetPNG(widget)}
              title="Tải ảnh PNG"
            >
              <Download className="w-3.5 h-3.5" />
            </Button>

            {/* Fullscreen / Inspect */}
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 rounded-md text-gray-500 hover:text-blue-600"
              onClick={() => { setSelectedWidget(widget); setModalTab('chart'); }}
              title="Xem chi tiết & SQL"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </Button>

            {/* Delete */}
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30"
              onClick={() => handleDeleteWidget(widget.id)}
              title="Xóa biểu đồ"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>

        {/* Chart View */}
        <div className="flex-1 min-h-0 w-full relative pt-1">
          {widget.chart_config ? (
            <ReactECharts 
              ref={(e) => { if (e) widgetChartRefs.current[widget.id] = e; }}
              option={option} 
              style={{ height: '100%', width: '100%' }}
              opts={{ renderer: 'canvas' }}
              notMerge={true}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400 text-xs">
              Chưa có dữ liệu biểu đồ
            </div>
          )}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-gray-500 flex items-center justify-center h-full gap-2">
        <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
        <span>Đang tải Dashboards...</span>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full bg-gray-50/50 dark:bg-gray-900/50">
      {/* Sidebar for dashboards list */}
      <div className="w-64 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-[#020817] flex flex-col shrink-0">
        <div className="p-3.5 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
          <h3 className="font-bold text-xs uppercase tracking-wider text-gray-500 flex items-center gap-2">
            <LayoutDashboard className="w-4 h-4 text-blue-600" /> 
            Danh sách Dashboards
          </h3>
          <Button variant="ghost" size="icon" onClick={() => setIsCreating(true)} className="h-7 w-7 rounded-lg text-blue-600 hover:text-blue-700 hover:bg-blue-50 dark:hover:bg-blue-950/30">
            <Plus className="w-4 h-4" />
          </Button>
        </div>

        {/* Create Dashboard Inline Form */}
        {isCreating && (
          <form onSubmit={handleCreateDashboardSubmit} className="p-3 border-b border-gray-200 dark:border-gray-800 bg-blue-50/50 dark:bg-blue-950/20 space-y-2">
            <div className="text-xs font-semibold text-blue-900 dark:text-blue-200">Tạo Dashboard mới</div>
            <Input
              placeholder="Tên Dashboard (vd: Sales Performance)..."
              value={newDashName}
              onChange={(e) => setNewDashName(e.target.value)}
              className="h-7 text-xs bg-white dark:bg-gray-900"
              autoFocus
            />
            <Input
              placeholder="Mô tả mục tiêu..."
              value={newDashDesc}
              onChange={(e) => setNewDashDesc(e.target.value)}
              className="h-7 text-xs bg-white dark:bg-gray-900"
            />
            <div className="flex items-center gap-1.5 justify-end pt-1">
              <Button type="button" variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => setIsCreating(false)}>
                Hủy
              </Button>
              <Button type="submit" size="sm" className="h-6 px-2.5 text-xs bg-blue-600 hover:bg-blue-700 text-white" disabled={isSubmitting || !newDashName.trim()}>
                {isSubmitting ? <Loader2 className="w-3 h-3 animate-spin" /> : "Tạo"}
              </Button>
            </div>
          </form>
        )}

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {dashboards.map(db => (
            <div 
              key={db.id} 
              className={cn(
                "p-2.5 rounded-xl cursor-pointer flex justify-between items-center transition-colors group",
                activeDashboard?.id === db.id 
                  ? "bg-blue-600 text-white shadow-sm font-semibold" 
                  : "hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 font-medium"
              )}
              onClick={async () => {
                const detail = await dashboardService.getDashboard(db.id);
                setActiveDashboard(detail);
              }}
            >
              <span className="truncate text-xs">{db.name}</span>
              <button 
                onClick={(e) => { e.stopPropagation(); handleDeleteDashboard(db.id); }} 
                className={cn(
                  "opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-500/20",
                  activeDashboard?.id === db.id ? "text-white" : "text-gray-400 hover:text-red-500"
                )}
                title="Xóa Dashboard"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          {dashboards.length === 0 && !isCreating && (
            <div className="text-center p-6 text-xs text-gray-400">
              Chưa có dashboard nào trong Workspace này.
            </div>
          )}
        </div>
      </div>

      {/* Main dashboard view */}
      <div className="flex-1 overflow-y-auto p-6 relative flex flex-col" ref={containerRef as any}>
        {activeDashboard ? (
          <div className="w-full flex-1 flex flex-col">
            {/* Top Header & Executive KPI Ribbon */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
              <div>
                <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <LayoutDashboard className="w-5 h-5 text-blue-600" />
                  {activeDashboard.name}
                </h1>
                {activeDashboard.description && <p className="text-gray-500 text-xs mt-1">{activeDashboard.description}</p>}
              </div>

              {/* Toolbar */}
              <div className="flex items-center gap-2 flex-wrap">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                  <Input 
                    placeholder="Tìm biểu đồ..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="h-8 pl-8 text-xs w-40 rounded-xl bg-white dark:bg-gray-900"
                  />
                </div>
                <Button size="sm" variant="outline" className="text-xs h-8 rounded-xl gap-1.5" onClick={() => window.print()} title="In / Xuất báo cáo PDF">
                  <Printer className="w-3.5 h-3.5 text-gray-500" />
                  In báo cáo
                </Button>
                <Button size="sm" variant="outline" className="text-xs h-8 rounded-xl gap-1.5" onClick={loadDashboards}>
                  <RefreshCw className="w-3 h-3 text-gray-500" />
                  Làm mới
                </Button>
                <Button size="sm" className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs h-8 gap-1.5 shadow-sm" onClick={() => navigate('/')}>
                  <Sparkles className="w-3.5 h-3.5" />
                  Hỏi AI để thêm biểu đồ
                </Button>
              </div>
            </div>

            {/* Quick KPI Metric Highlights */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <div className="p-3.5 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl shadow-sm flex items-center justify-between">
                <div>
                  <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Tổng số biểu đồ</div>
                  <div className="text-xl font-bold text-gray-900 dark:text-white mt-1">{activeDashboard.widgets?.length || 0}</div>
                </div>
                <div className="p-2 rounded-xl bg-blue-50 dark:bg-blue-950/40 text-blue-600">
                  <BarChart2 className="w-5 h-5" />
                </div>
              </div>
              <div className="p-3.5 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl shadow-sm flex items-center justify-between">
                <div>
                  <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Cơ sở dữ liệu</div>
                  <div className="text-sm font-bold text-blue-600 mt-1 truncate max-w-[120px]">{selectedGraph?.name || 'Mặc định'}</div>
                </div>
                <div className="p-2 rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600">
                  <Database className="w-5 h-5" />
                </div>
              </div>
              <div className="p-3.5 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl shadow-sm flex items-center justify-between">
                <div>
                  <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Trạng thái đồng bộ</div>
                  <div className="text-sm font-semibold text-emerald-600 mt-1 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    Sẵn sàng
                  </div>
                </div>
                <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
              </div>
              <div className="p-3.5 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl shadow-sm flex items-center justify-between">
                <div>
                  <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Tốc độ phản hồi</div>
                  <div className="text-sm font-bold text-purple-600 mt-1">~0.4s (Flash)</div>
                </div>
                <div className="p-2 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-600">
                  <TrendingUp className="w-5 h-5" />
                </div>
              </div>
            </div>
            
            {/* Grid Layout of Widgets */}
            {mounted && filteredWidgets.length > 0 ? (
              <Responsive
                className="layout"
                width={width}
                layouts={{
                  lg: filteredWidgets.map(w => ({
                    i: w.id,
                    x: w.layout?.x || 0,
                    y: w.layout?.y || 0,
                    w: w.layout?.w || 6,
                    h: w.layout?.h || 4
                  }))
                }}
                breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
                rowHeight={100}
                dragConfig={{ handle: ".drag-handle" }}
                onLayoutChange={handleLayoutChange as any}
              >
                {filteredWidgets.map(renderWidget)}
              </Responsive>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-center border-2 border-dashed border-gray-200 dark:border-gray-800 rounded-3xl bg-white dark:bg-gray-900/40 min-h-[360px]">
                <div className="w-16 h-16 rounded-3xl bg-blue-50 dark:bg-blue-950/40 text-blue-600 flex items-center justify-center mb-4 shadow-inner">
                  <LayoutDashboard className="w-8 h-8" />
                </div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-1">
                  {searchQuery ? "Không tìm thấy biểu đồ khớp với tìm kiếm" : "Dashboard này chưa có biểu đồ"}
                </h3>
                <p className="text-gray-500 text-xs max-w-md mb-6 leading-relaxed">
                  {searchQuery 
                    ? "Thử tìm kiếm với từ khóa khác hoặc xóa bộ lọc." 
                    : "Bạn có thể nạp ngay gói biểu đồ mẫu (Doanh thu, Top SP, Nhóm hàng) hoặc hỏi AI bất kỳ câu hỏi nào để ghim biểu đồ mới."}
                </p>
                {!searchQuery && (
                  <div className="flex items-center gap-3 flex-wrap justify-center">
                    <Button 
                      size="sm" 
                      variant="outline"
                      className="rounded-xl text-xs h-9 px-4 border-blue-200 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40 gap-1.5"
                      onClick={handleSeedStarterPack}
                      disabled={isSeeding}
                    >
                      {isSeeding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                      ✨ Nạp bộ chỉ số mẫu (Starter Pack)
                    </Button>
                    <Button 
                      size="sm" 
                      className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs h-9 px-4 gap-1.5 shadow-sm" 
                      onClick={() => navigate('/')}
                    >
                      <ArrowUpRight className="w-3.5 h-3.5" />
                      Hỏi đáp AI ngay
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col h-full items-center justify-center text-center p-8">
            <LayoutDashboard className="w-14 h-14 text-gray-300 dark:text-gray-700 mb-3" />
            <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200 mb-1">Chưa có Dashboard nào</h3>
            <p className="text-gray-500 text-xs max-w-sm mb-4">Tạo Dashboard đầu tiên của bạn để gom các báo cáo và biểu đồ vào một nơi.</p>
            <Button size="sm" className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs h-8" onClick={() => setIsCreating(true)}>
              <Plus className="w-3.5 h-3.5 mr-1.5" />
              Tạo Dashboard mới
            </Button>
          </div>
        )}
      </div>

      {/* Fullscreen / Inspect Widget Modal */}
      {selectedWidget && (
        <Dialog open={!!selectedWidget} onOpenChange={(open) => !open && setSelectedWidget(null)}>
          <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col p-6 rounded-3xl">
            <DialogHeader className="border-b border-gray-100 dark:border-gray-800 pb-3">
              <div className="flex items-center justify-between pr-6 flex-wrap gap-2">
                <div>
                  <DialogTitle className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                    <BarChart2 className="w-5 h-5 text-blue-600" />
                    {selectedWidget.title}
                  </DialogTitle>
                  <DialogDescription className="text-xs text-gray-500 mt-0.5">
                    Chi tiết biểu đồ trực quan và câu lệnh SQL truy vấn dữ liệu gốc
                  </DialogDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs rounded-xl"
                    onClick={() => handleExportWidgetCSV(selectedWidget)}
                  >
                    <Download className="w-3.5 h-3.5 mr-1" />
                    Xuất CSV
                  </Button>
                  <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 p-1 rounded-xl">
                    <Button
                      variant={modalTab === 'chart' ? 'secondary' : 'ghost'}
                      size="sm"
                      className="h-7 text-xs rounded-lg"
                      onClick={() => setModalTab('chart')}
                    >
                      <Eye className="w-3.5 h-3.5 mr-1.5" />
                      Biểu đồ
                    </Button>
                    <Button
                      variant={modalTab === 'sql' ? 'secondary' : 'ghost'}
                      size="sm"
                      className="h-7 text-xs rounded-lg"
                      onClick={() => setModalTab('sql')}
                    >
                      <Code className="w-3.5 h-3.5 mr-1.5" />
                      Câu lệnh SQL
                    </Button>
                  </div>
                </div>
              </div>
            </DialogHeader>

            <div className="flex-1 min-h-[400px] py-4 overflow-y-auto">
              {modalTab === 'chart' ? (
                <div className="h-[420px] w-full">
                  {selectedWidget.chart_config ? (
                    <ReactECharts 
                      option={getTransformedOption(selectedWidget)} 
                      style={{ height: '100%', width: '100%' }}
                      opts={{ renderer: 'canvas' }}
                      notMerge={true}
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-400 text-sm">Chưa có biểu đồ</div>
                  )}
                </div>
              ) : (
                <div className="relative bg-gray-950 text-gray-100 p-5 rounded-2xl font-mono text-xs overflow-x-auto leading-relaxed border border-gray-800">
                  <div className="absolute top-3 right-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs bg-gray-800 hover:bg-gray-700 text-gray-200"
                      onClick={() => {
                        if (selectedWidget.sql_query) {
                          navigator.clipboard.writeText(selectedWidget.sql_query);
                          setCopiedSql(true);
                          setTimeout(() => setCopiedSql(false), 2000);
                          toast({ title: "Đã copy SQL", description: "Câu lệnh SQL đã được lưu vào bộ nhớ tạm." });
                        }
                      }}
                    >
                      {copiedSql ? (
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
                  <pre>{selectedWidget.sql_query || "Chưa lưu câu lệnh SQL cho biểu đồ này."}</pre>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default V4Dashboards;
