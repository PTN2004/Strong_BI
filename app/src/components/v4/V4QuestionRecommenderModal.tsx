import React, { useState, useEffect, useMemo } from 'react';
import { 
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription 
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { 
  Sparkles, Search, RefreshCw, BarChart2, LineChart, PieChart, 
  Layers, TrendingUp, AlertTriangle, Trophy, 
  HelpCircle, Database, Loader2, ChevronRight, Zap,
  Table2, Target, GitBranch, Compass, ArrowRight
} from 'lucide-react';
import { buildApiUrl } from '@/config/api';
import { useSettings } from '@/contexts/SettingsContext';
import { toast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';

export interface TableSummaryItem {
  name: string;
  columns_count?: number;
  sample_columns?: string[];
}

export interface RecommendedQuestion {
  id: string;
  question: string;
  category: 'kpi' | 'breakdown' | 'trend' | 'ranking' | 'anomaly';
  category_label?: string;
  description: string;
  business_value?: string;
  metrics?: string[];
  dimensions?: string[];
  chart_type?: string;
  complexity?: string;
  tables?: string[];
  follow_ups?: string[];
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  graphId: string;
  graphName?: string;
  onSelectQuestion: (question: string) => void;
}

const CATEGORY_TABS = [
  { id: 'all', label: 'Tất cả câu hỏi', icon: Sparkles },
  { id: 'kpi', label: 'Chỉ số KPI cốt lõi', icon: TrendingUp },
  { id: 'breakdown', label: 'Phân tích đa chiều', icon: Layers },
  { id: 'trend', label: 'Xu hướng thời gian', icon: LineChart },
  { id: 'ranking', label: 'Xếp hạng Top / Bottom', icon: Trophy },
  { id: 'anomaly', label: 'Cảnh báo rủi ro', icon: AlertTriangle },
];

const PRESET_TOPICS = [
  'Doanh thu & Đơn hàng',
  'Khách hàng & VIP',
  'Sản phẩm & Danh mục',
  'Tồn kho & Kho vận',
  'Khu vực & Chi nhánh',
];

export const V4QuestionRecommenderModal: React.FC<Props> = ({
  open,
  onOpenChange,
  graphId,
  graphName,
  onSelectQuestion
}) => {
  const { isApiKeyValid, apiKey, modelName, customEndpoint } = useSettings();
  const [questions, setQuestions] = useState<RecommendedQuestion[]>([]);
  const [tablesSummary, setTablesSummary] = useState<TableSummaryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [customFocus, setCustomFocus] = useState<string>('');

  const fetchRecommendations = async (focusText?: string) => {
    if (!graphId) return;
    try {
      setLoading(true);
      const res = await fetch(buildApiUrl(`/graphs/${graphId}/suggest_questions`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          focus: focusText ?? customFocus,
          custom_api_key: isApiKeyValid ? (apiKey || undefined) : undefined,
          custom_model: isApiKeyValid ? (modelName || undefined) : undefined,
          custom_api_base: isApiKeyValid ? (customEndpoint || undefined) : undefined,
        }),
      });

      if (!res.ok) throw new Error('Không thể tạo gợi ý câu hỏi');
      const data = await res.json();
      if (data.recommendations && Array.isArray(data.recommendations)) {
        setQuestions(data.recommendations);
      }
      if (data.tables_summary && Array.isArray(data.tables_summary)) {
        setTablesSummary(data.tables_summary);
      }
    } catch (e: any) {
      toast({
        title: 'Thông báo',
        description: 'Đang tải bộ câu hỏi phân tích kinh doanh tiêu chuẩn cho cơ sở dữ liệu.',
      });
      // Standard rich executive fallbacks
      setQuestions([
        {
          id: "fb_1",
          question: "Tổng doanh thu và số lượng đơn hàng 30 ngày qua",
          category: "kpi",
          category_label: "Chỉ số KPI",
          description: "Đo lường sức khỏe doanh số và tốc độ phát sinh đơn hàng trong chu kỳ gần nhất",
          business_value: "Đánh giá hiệu suất kinh doanh tức thời và cảnh báo sớm biến động dòng tiền doanh nghiệp",
          metrics: ["Tổng doanh thu", "Số lượng đơn hàng", "AOV (Giá trị trung bình/đơn)"],
          dimensions: ["Ngày đặt hàng"],
          chart_type: "bar",
          complexity: "Cơ bản",
          tables: ["orders"],
          follow_ups: ["Doanh thu ngày nào cao nhất trong tuần?", "Tỷ lệ đơn hàng giao thành công theo ngày?"]
        },
        {
          id: "fb_2",
          question: "Top 10 sản phẩm có doanh thu cao nhất tháng này",
          category: "ranking",
          category_label: "Xếp hạng",
          description: "Nhận diện danh mục mặt hàng chủ lực đóng góp lớn nhất vào tổng doanh thu",
          business_value: "Tối ưu hóa kế hoạch nhập hàng và phân bổ ngân sách tiếp thị cho sản phẩm Hero",
          metrics: ["Doanh số bán", "Số lượng bán ra", "Biên đóng góp"],
          dimensions: ["Tên sản phẩm", "Nhóm danh mục"],
          chart_type: "bar",
          complexity: "Cơ bản",
          tables: ["order_items", "products"],
          follow_ups: ["Biên lợi nhuận của Top 10 sản phẩm này?", "Khách hàng nào mua nhiều nhất các sản phẩm này?"]
        },
        {
          id: "fb_3",
          question: "Tỷ trọng doanh số theo từng nhóm danh mục sản phẩm",
          category: "breakdown",
          category_label: "Phân tích đa chiều",
          description: "Phân tích cơ cấu đóng góp của từng dòng sản phẩm để tối ưu danh mục kinh doanh",
          business_value: "Giúp Ban Lãnh đạo đánh giá mức độ phụ thuộc danh mục và đa dạng hóa sản phẩm",
          metrics: ["Tỷ trọng % doanh thu", "Tổng giá trị danh mục"],
          dimensions: ["Danh mục ngành hàng"],
          chart_type: "pie",
          complexity: "Cơ bản",
          tables: ["products", "order_items"],
          follow_ups: ["Danh mục nào có tốc độ tăng trưởng nhanh nhất?", "Tồn kho tương ứng của từng danh mục?"]
        },
        {
          id: "fb_4",
          question: "Xu hướng tăng trưởng đơn hàng theo tuần trong quý này",
          category: "trend",
          category_label: "Xu hướng",
          description: "Phân tích chu kỳ dao động và tốc độ tăng trưởng quy mô bán hàng theo thời gian",
          business_value: "Dự báo nhu cầu nhân sự vận hành kho vận và kế hoạch bán lẻ các tuần tiếp theo",
          metrics: ["Số lượng đơn hàng", "Tốc độ tăng trưởng tuần (WoW)"],
          dimensions: ["Tuần trong quý"],
          chart_type: "area",
          complexity: "Nâng cao",
          tables: ["orders"],
          follow_ups: ["Nguyên nhân các tuần sụt giảm đơn hàng?", "Khung giờ đặt hàng cao điểm trong tuần?"]
        },
        {
          id: "fb_5",
          question: "Top 10 khách hàng có giá trị mua sắm lớn nhất",
          category: "ranking",
          category_label: "Xếp hạng",
          description: "Định vị và chăm sóc tệp khách hàng VIP mang lại giá trị vòng đời cao nhất",
          business_value: "Thiết lập chính sách chăm sóc khách hàng đặc biệt và giữ chân khách hàng then chốt",
          metrics: ["Tổng chi tiêu tích lũy", "Tần suất mua hàng"],
          dimensions: ["Khách hàng", "Khu vực địa lý"],
          chart_type: "bar",
          complexity: "Cơ bản",
          tables: ["customers", "orders"],
          follow_ups: ["Chu kỳ quay lại mua hàng của tệp VIP này?", "Mặt hàng ưa thích của nhóm VIP?"]
        },
        {
          id: "fb_6",
          question: "Các sản phẩm có lượng tồn kho cao nhưng doanh số bán thấp",
          category: "anomaly",
          category_label: "Cảnh báo rủi ro",
          description: "Cảnh báo các mặt hàng có nguy cơ đọng vốn và chi phí lưu kho kéo dài",
          business_value: "Kịp thời tung chương trình khuyến mãi xả hàng giải phóng dòng tiền lưu động",
          metrics: ["Số lượng tồn kho", "Doanh số 30 ngày qua", "Thời gian lưu kho"],
          dimensions: ["Sản phẩm", "Kho lưu trữ"],
          chart_type: "bar",
          complexity: "Nâng cao",
          tables: ["products", "inventory"],
          follow_ups: ["Tổng giá trị vốn đang bị đọng là bao nhiêu?", "Đề xuất mức giảm giá tối ưu để thu hồi vốn?"]
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && graphId && questions.length === 0) {
      fetchRecommendations();
    }
  }, [open, graphId]);

  const filteredQuestions = useMemo(() => {
    return questions.filter((q: RecommendedQuestion) => {
      const matchCat = activeCategory === 'all' || q.category === activeCategory;
      const matchTable = !selectedTable || (q.tables && q.tables.some((t: string) => t.toLowerCase() === selectedTable.toLowerCase()));
      const matchSearch = !searchFilter.trim() || 
        q.question.toLowerCase().includes(searchFilter.toLowerCase()) ||
        q.description.toLowerCase().includes(searchFilter.toLowerCase()) ||
        (q.business_value && q.business_value.toLowerCase().includes(searchFilter.toLowerCase())) ||
        (q.tables && q.tables.some((t: string) => t.toLowerCase().includes(searchFilter.toLowerCase())));
      return matchCat && matchTable && matchSearch;
    });
  }, [questions, activeCategory, selectedTable, searchFilter]);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: questions.length };
    questions.forEach((q: RecommendedQuestion) => {
      counts[q.category] = (counts[q.category] || 0) + 1;
    });
    return counts;
  }, [questions]);

  const getChartIcon = (type?: string) => {
    switch (type) {
      case 'line': return <LineChart className="w-4 h-4" />;
      case 'area': return <Layers className="w-4 h-4" />;
      case 'pie': return <PieChart className="w-4 h-4" />;
      default: return <BarChart2 className="w-4 h-4" />;
    }
  };

  const getCategoryBadgeClass = (category: string) => {
    switch (category) {
      case 'kpi':
        return 'bg-blue-50 text-blue-700 dark:bg-blue-950/70 dark:text-blue-300 border-blue-200/80 dark:border-blue-800/80';
      case 'ranking':
        return 'bg-amber-50 text-amber-700 dark:bg-amber-950/70 dark:text-amber-300 border-amber-200/80 dark:border-amber-800/80';
      case 'breakdown':
        return 'bg-purple-50 text-purple-700 dark:bg-purple-950/70 dark:text-purple-300 border-purple-200/80 dark:border-purple-800/80';
      case 'trend':
        return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300 border-emerald-200/80 dark:border-emerald-800/80';
      case 'anomaly':
        return 'bg-rose-50 text-rose-700 dark:bg-rose-950/70 dark:text-rose-300 border-rose-200/80 dark:border-rose-800/80';
      default:
        return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-700';
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[98vw] max-w-[1550px] sm:max-w-[1550px] h-[93vh] max-h-[960px] flex flex-col p-0 rounded-3xl overflow-hidden border border-gray-200/80 dark:border-gray-800 bg-white dark:bg-[#0c0c0e] shadow-2xl">
        {/* Top Studio Bar */}
        <DialogHeader className="px-6 py-4 border-b border-gray-100 dark:border-gray-800/80 bg-gray-50/50 dark:bg-[#111114] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-blue-600 via-indigo-600 to-violet-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/20 ring-4 ring-blue-500/10 shrink-0">
              <Compass className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <DialogTitle className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white tracking-tight">
                  Trung tâm Khám phá & Gợi ý Câu hỏi Dữ liệu
                </DialogTitle>
                <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200/60 dark:border-blue-900/60">
                  AI Analytics Studio
                </span>
              </div>
              <DialogDescription className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Mô hình đang phân tích cơ sở dữ liệu: <span className="font-semibold text-gray-800 dark:text-gray-200">{graphName || 'Cơ sở dữ liệu đang chọn'}</span>
              </DialogDescription>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-auto">
            <Button
              size="sm"
              variant="outline"
              className="text-xs h-9 px-3.5 rounded-xl gap-2 border-gray-200 dark:border-gray-700 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50/50 dark:hover:bg-blue-950/30 transition-all shadow-sm"
              onClick={() => fetchRecommendations()}
              disabled={loading}
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              <span>AI Quét lại Schema & Gợi ý mới</span>
            </Button>
          </div>
        </DialogHeader>

        {/* Studio Body: Left Sidebar (Schema & Presets) + Main Discovery Canvas */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel: Schema Explorer & Quick Presets */}
          <div className="w-72 sm:w-80 border-r border-gray-100 dark:border-gray-800/80 bg-gray-50/30 dark:bg-[#0f0f12] flex flex-col p-4 overflow-y-auto shrink-0 hidden md:flex gap-5">
            {/* Database & Schema Status */}
            <div className="p-3.5 rounded-2xl bg-white dark:bg-[#16161a] border border-gray-200/80 dark:border-gray-800 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">Trạng thái CSDL</span>
                <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  Sẵn sàng
                </span>
              </div>
              <div className="text-xs font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-1.5">
                <Database className="w-4 h-4 text-blue-600" />
                <span className="truncate">{graphName || 'CSDL Doanh nghiệp'}</span>
              </div>
              <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-800 text-[11px] text-gray-400 flex items-center justify-between">
                <span>{tablesSummary.length > 0 ? `${tablesSummary.length} Bảng dữ liệu` : 'Đa bảng liên kết'}</span>
                <span>{questions.length} Câu hỏi sẵn sàng</span>
              </div>
            </div>

            {/* Quick Topic Filters */}
            <div>
              <div className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-amber-500" />
                Chủ đề Phân tích Nhanh
              </div>
              <div className="flex flex-wrap gap-1.5">
                {PRESET_TOPICS.map((topic: string) => (
                  <button
                    key={topic}
                    type="button"
                    onClick={() => {
                      setCustomFocus(topic);
                      fetchRecommendations(topic);
                    }}
                    className="text-xs px-2.5 py-1.5 rounded-xl border border-gray-200/80 dark:border-gray-800 bg-white dark:bg-[#16161a] text-gray-600 dark:text-gray-300 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-400 transition-all text-left"
                  >
                    {topic}
                  </button>
                ))}
              </div>
            </div>

            {/* Tables Explorer */}
            {tablesSummary.length > 0 && (
              <div className="flex-1 flex flex-col min-h-0">
                <div className="flex items-center justify-between text-xs font-bold text-gray-500 uppercase tracking-wider mb-2.5">
                  <div className="flex items-center gap-1.5">
                    <Table2 className="w-3.5 h-3.5 text-blue-500" />
                    Bảng Dữ liệu ({tablesSummary.length})
                  </div>
                  {selectedTable && (
                    <button
                      type="button"
                      onClick={() => setSelectedTable(null)}
                      className="text-[11px] text-blue-600 hover:underline capitalize"
                    >
                      Bỏ lọc
                    </button>
                  )}
                </div>
                <div className="space-y-1.5 overflow-y-auto pr-1">
                  {tablesSummary.map((tbl: TableSummaryItem) => {
                    const isSelected = selectedTable === tbl.name;
                    return (
                      <button
                        key={tbl.name}
                        type="button"
                        onClick={() => setSelectedTable(isSelected ? null : tbl.name)}
                        className={cn(
                          "w-full text-left p-2.5 rounded-xl border text-xs transition-all flex flex-col gap-1",
                          isSelected
                            ? "bg-blue-50 dark:bg-blue-950/50 border-blue-500 text-blue-700 dark:text-blue-300 shadow-sm"
                            : "bg-white dark:bg-[#16161a] border-gray-200/70 dark:border-gray-800/80 text-gray-700 dark:text-gray-300 hover:border-gray-300 dark:hover:border-gray-700"
                        )}
                      >
                        <div className="flex items-center justify-between font-semibold">
                          <span className="truncate">{tbl.name}</span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-gray-100 dark:bg-gray-800 text-gray-500">
                            {tbl.columns_count || 0} cột
                          </span>
                        </div>
                        {tbl.sample_columns && tbl.sample_columns.length > 0 && (
                          <div className="text-[10px] text-gray-400 truncate">
                            {tbl.sample_columns.join(', ')}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Main Content Area */}
          <div className="flex-1 flex flex-col p-6 overflow-hidden bg-white dark:bg-[#0c0c0e]">
            {/* Search & Topic Bar */}
            <div className="flex flex-col sm:flex-row items-center gap-3 mb-4">
              <div className="relative flex-1 w-full">
                <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <Input
                  placeholder="Tìm kiếm câu hỏi, chỉ số, bảng dữ liệu hoặc mục tiêu phân tích..."
                  value={searchFilter}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchFilter(e.target.value)}
                  className="h-10 pl-10 pr-3 text-xs sm:text-sm rounded-xl bg-gray-50/80 dark:bg-[#16161a] border-gray-200/80 dark:border-gray-800 focus:bg-white dark:focus:bg-[#16161a] transition-colors"
                />
              </div>
              <form 
                onSubmit={(e: React.FormEvent) => { e.preventDefault(); fetchRecommendations(customFocus); }} 
                className="flex items-center gap-2 w-full sm:w-auto"
              >
                <Input
                  placeholder="Nhập chủ đề tùy chỉnh (vd: Doanh số tháng 9, Bán sỉ)..."
                  value={customFocus}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCustomFocus(e.target.value)}
                  className="h-10 text-xs sm:text-sm w-full sm:w-64 rounded-xl bg-gray-50/80 dark:bg-[#16161a] border-gray-200/80 dark:border-gray-800"
                />
                <Button 
                  type="submit" 
                  size="sm" 
                  className="h-10 px-4 text-xs sm:text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-xl shrink-0 shadow-md shadow-blue-500/20 transition-all" 
                  disabled={loading}
                >
                  <Zap className="w-4 h-4 mr-1.5" />
                  Gợi ý
                </Button>
              </form>
            </div>

            {/* Category Filter Tabs */}
            <div className="flex items-center gap-2 overflow-x-auto pb-3 mb-2 scrollbar-none border-b border-gray-100 dark:border-gray-800/80">
              {CATEGORY_TABS.map((tab) => {
                const Icon = tab.icon;
                const active = activeCategory === tab.id;
                const count = categoryCounts[tab.id] || 0;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveCategory(tab.id)}
                    className={cn(
                      "flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all border",
                      active
                        ? "bg-gray-900 text-white dark:bg-white dark:text-gray-900 border-gray-900 dark:border-white shadow-sm"
                        : "bg-gray-50/80 dark:bg-[#16161a] text-gray-600 dark:text-gray-400 border-gray-200/70 dark:border-gray-800 hover:bg-gray-100/70 dark:hover:bg-gray-800"
                    )}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{tab.label}</span>
                    {count > 0 && (
                      <span className={cn(
                        "text-[10px] px-1.5 py-0.2 rounded-full font-bold",
                        active
                          ? "bg-white/20 text-white dark:bg-gray-900/20 dark:text-gray-900"
                          : "bg-gray-200/80 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
                      )}>
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Questions Grid Canvas */}
            <div className="flex-1 overflow-y-auto pr-1">
              {loading ? (
                <div className="flex flex-col items-center justify-center h-full text-center gap-3">
                  <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
                  <div className="text-base font-bold text-gray-800 dark:text-gray-200">
                    AI đang phân tích mô hình quan hệ bảng và lập danh mục câu hỏi phân tích...
                  </div>
                  <p className="text-xs text-gray-400 max-w-md">
                    Đang đối chiếu các trường số liệu, chiều phân loại và mục tiêu điều hành kinh doanh của doanh nghiệp.
                  </p>
                </div>
              ) : filteredQuestions.length > 0 ? (
                <div className="flex flex-col gap-0 pb-10">
                  {filteredQuestions.map((item: RecommendedQuestion) => (
                    <div
                      key={item.id}
                      className="py-7 border-b border-gray-100 dark:border-gray-800/60 last:border-0 flex flex-col gap-3 hover:bg-gray-50/50 dark:hover:bg-[#16161a]/80 px-5 -mx-5 rounded-3xl transition-all group"
                    >
                      {/* Header: Category and Complexity */}
                      <div className="flex items-center gap-3">
                        <span className={cn("text-[11px] font-bold px-2.5 py-0.5 rounded-lg border", getCategoryBadgeClass(item.category))}>
                          {item.category_label || item.category.toUpperCase()}
                        </span>
                        {item.complexity && (
                          <span className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 px-2 py-0.5 rounded-lg bg-gray-100 dark:bg-gray-800/80 border border-gray-200/60 dark:border-gray-700/60">
                            {item.complexity}
                          </span>
                        )}
                        <div className="flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400 font-medium ml-2">
                          {getChartIcon(item.chart_type)}
                          <span className="capitalize">{item.chart_type === 'bar' ? 'Biểu đồ Cột' : item.chart_type === 'line' ? 'Biểu đồ Đường' : item.chart_type === 'pie' ? 'Biểu đồ Tròn' : 'Biểu đồ Miền'}</span>
                        </div>
                      </div>

                      {/* Title & Description */}
                      <h3 className="text-xl font-bold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors leading-tight cursor-pointer mt-1"
                          onClick={() => {
                            onSelectQuestion(item.question);
                            onOpenChange(false);
                          }}
                      >
                        {item.question}
                      </h3>
                      
                      <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed max-w-5xl">
                        {item.description}
                      </p>

                      {/* Business Value (Mục tiêu) */}
                      {item.business_value && (
                         <div className="flex items-start gap-2 mt-2">
                           <Target className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                           <div className="text-sm text-gray-700 dark:text-gray-300">
                             <span className="font-semibold text-gray-900 dark:text-white">Mục tiêu phân tích: </span>
                             {item.business_value}
                           </div>
                         </div>
                      )}

                      {/* Metrics and Dimensions - inline */}
                      {(item.metrics || item.dimensions) && (
                        <div className="flex flex-wrap items-center gap-2 mt-2">
                          <div className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mr-1">Chỉ số & Chiều:</div>
                          {item.metrics && item.metrics.map((m: string, i: number) => (
                            <span key={`m-${i}`} className="px-2.5 py-1 rounded-md bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 border border-emerald-100 dark:border-emerald-900/40 text-[11px] font-semibold">
                              {m}
                            </span>
                          ))}
                          {item.dimensions && item.dimensions.map((d: string, i: number) => (
                            <span key={`d-${i}`} className="px-2.5 py-1 rounded-md bg-indigo-50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-300 border border-indigo-100 dark:border-indigo-900/40 text-[11px] font-semibold">
                              {d}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Follow up & Execution Button Row */}
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mt-4 pt-4 border-t border-gray-100 dark:border-gray-800/50">
                         {/* Follow-up Questions */}
                         <div className="flex-1">
                          {item.follow_ups && item.follow_ups.length > 0 && (
                            <div className="flex flex-wrap items-center gap-2">
                              <GitBranch className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                              <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mr-1">Gợi ý đào sâu:</span>
                              {item.follow_ups.map((fq: string, fi: number) => (
                                <button
                                  key={fi}
                                  type="button"
                                  onClick={(e: React.MouseEvent) => {
                                    e.stopPropagation();
                                    onSelectQuestion(fq);
                                    onOpenChange(false);
                                  }}
                                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 font-medium"
                                >
                                  <ArrowRight className="w-3 h-3" />
                                  {fq}
                                </button>
                              ))}
                            </div>
                          )}
                         </div>

                         {/* Button */}
                         <div className="flex items-center gap-4 shrink-0">
                            <div className="flex items-center gap-1.5 text-[11px] text-gray-400 bg-gray-50 dark:bg-gray-800/50 px-2.5 py-1.5 rounded-lg border border-gray-200/50 dark:border-gray-700/50">
                              <Database className="w-3.5 h-3.5 text-gray-400" />
                              <span className="font-mono">{item.tables?.join(', ') || 'Tự động liên kết'}</span>
                            </div>
                            <Button
                              size="sm"
                              onClick={() => {
                                onSelectQuestion(item.question);
                                onOpenChange(false);
                              }}
                              className="h-10 px-5 text-xs font-bold bg-gray-900 hover:bg-blue-600 dark:bg-white dark:text-gray-900 dark:hover:bg-blue-500 dark:hover:text-white text-white rounded-xl gap-1.5 transition-all shadow-md hover:scale-105"
                            >
                              <span>Thực thi AI</span>
                              <Zap className="w-4 h-4" />
                            </Button>
                         </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-center p-8 border-2 border-dashed border-gray-200 dark:border-gray-800 rounded-3xl">
                  <HelpCircle className="w-12 h-12 text-gray-300 dark:text-gray-700 mb-3" />
                  <div className="text-base font-bold text-gray-800 dark:text-gray-200">Không tìm thấy câu hỏi phù hợp</div>
                  <p className="text-xs text-gray-400 max-w-sm mt-1 mb-4">
                    Thử đổi danh mục lọc, chọn bảng khác hoặc tìm kiếm bằng từ khóa kinh doanh khác.
                  </p>
                  <Button 
                    size="sm" 
                    variant="outline" 
                    className="text-xs rounded-xl" 
                    onClick={() => { setSearchFilter(''); setActiveCategory('all'); setSelectedTable(null); }}
                  >
                    Xem tất cả gợi ý
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
