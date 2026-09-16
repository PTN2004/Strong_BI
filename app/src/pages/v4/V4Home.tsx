import React, { useEffect, useState } from 'react';
import { useDatabase } from '@/contexts/DatabaseContext';
import { useAuth } from '@/contexts/AuthContext';
import { LayoutDashboard, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import ReactECharts from 'echarts-for-react';

interface PinnedChart {
  id: string;
  question: string;
  chartConfig: any;
  createdAt: string;
}

const V4Home = () => {
  const { selectedGraph } = useDatabase();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [pinnedCharts, setPinnedCharts] = useState<PinnedChart[]>([]);

  useEffect(() => {
    if (!selectedGraph) return;
    try {
      const pinKey = `pinned_charts_${selectedGraph.id}`;
      const raw = localStorage.getItem(pinKey);
      if (raw) {
        setPinnedCharts(JSON.parse(raw));
      }
    } catch (e) {
      console.error("Failed to load pinned charts", e);
    }
  }, [selectedGraph]);

  const handleUnpin = (id: string) => {
    if (!selectedGraph) return;
    const newCharts = pinnedCharts.filter(c => c.id !== id);
    setPinnedCharts(newCharts);
    localStorage.setItem(`pinned_charts_${selectedGraph.id}`, JSON.stringify(newCharts));
  };

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-900 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center">
              <LayoutDashboard className="w-8 h-8 mr-3 text-blue-600" />
              Tổng quan Dashboard
            </h1>
            <p className="text-gray-500 mt-2">
              Chào mừng trở lại! Dưới đây là các biểu đồ quan trọng bạn đã lưu.
            </p>
          </div>
          <Button 
            className="bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg shadow-blue-600/20 px-6 h-12"
            onClick={() => navigate('/chat')}
          >
            <Plus className="w-5 h-5 mr-2" />
            Hội thoại mới
          </Button>
        </div>

        {!selectedGraph ? (
          <div className="text-center py-20 bg-white dark:bg-gray-800 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm">
            <LayoutDashboard className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <h3 className="text-xl font-medium text-gray-900 dark:text-gray-100">Vui lòng chọn cơ sở dữ liệu</h3>
            <p className="text-gray-500 mt-2">Chọn một cơ sở dữ liệu từ thanh bên trái để xem Dashboard.</p>
          </div>
        ) : pinnedCharts.length === 0 ? (
          <div className="text-center py-20 bg-white dark:bg-gray-800 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm">
            <LayoutDashboard className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <h3 className="text-xl font-medium text-gray-900 dark:text-gray-100">Dashboard trống</h3>
            <p className="text-gray-500 mt-2">Bạn chưa ghim biểu đồ nào. Hãy bắt đầu chat và ghim các biểu đồ quan trọng nhé!</p>
            <Button 
              variant="outline" 
              className="mt-6 border-blue-200 text-blue-600 hover:bg-blue-50"
              onClick={() => navigate('/chat')}
            >
              Tạo biểu đồ ngay
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-6">
            {pinnedCharts.map(chart => (
              <div key={chart.id} className="bg-white dark:bg-gray-800 rounded-3xl border border-gray-100 dark:border-gray-700 shadow-sm overflow-hidden flex flex-col group">
                <div className="px-6 py-4 border-b border-gray-50 dark:border-gray-700/50 flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 line-clamp-2">
                      {chart.question}
                    </h3>
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(chart.createdAt).toLocaleString('vi-VN')}
                    </p>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8 text-gray-400 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => handleUnpin(chart.id)}
                    title="Bỏ ghim"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
                <div className="p-4 flex-1 min-h-[350px]">
                  <ReactECharts
                    option={chart.chartConfig}
                    style={{ height: '350px', width: '100%' }}
                    opts={{ renderer: 'svg' }}
                    notMerge={true}
                    lazyUpdate={true}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default V4Home;
