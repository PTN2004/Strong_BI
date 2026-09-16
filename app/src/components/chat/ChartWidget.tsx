import React, { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { Card, CardContent } from '@/components/ui/card';
import { BarChart3, Pin } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { dashboardService } from '@/services/dashboard';
import { Dashboard } from '@/types/api';
import { toast } from '@/components/ui/use-toast';
import { sanitizeEChartsFormatter } from '@/lib/utils';

interface ChartWidgetProps {
  chartConfig: any;
}

const ChartWidget: React.FC<ChartWidgetProps> = ({ chartConfig }) => {
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [showDashboards, setShowDashboards] = useState(false);
  const [pinning, setPinning] = useState(false);

  useEffect(() => {
    if (showDashboards && dashboards.length === 0) {
      dashboardService.getDashboards().then(setDashboards).catch(console.error);
    }
  }, [showDashboards]);

  const handlePin = async (dashboardId: string) => {
    try {
      setPinning(true);
      await dashboardService.addWidget(dashboardId, {
        title: chartConfig.title?.text || "New Chart",
        chart_type: "echarts",
        chart_config: chartConfig,
        layout_w: 6,
        layout_h: 4
      });
      toast({ title: 'Thành công', description: 'Đã ghim biểu đồ vào Dashboard' });
      setShowDashboards(false);
    } catch (e) {
      toast({ title: 'Lỗi', description: 'Không thể ghim biểu đồ', variant: 'destructive' });
    } finally {
      setPinning(false);
    }
  };

  if (!chartConfig) return null;

  const sanitizedConfig = sanitizeEChartsFormatter(chartConfig);

  // Enhance the chart config with a modern corporate theme
  const enhancedConfig = {
    ...sanitizedConfig,
    backgroundColor: 'transparent',
    textStyle: {
      fontFamily: 'Inter, sans-serif'
    },
    tooltip: {
      trigger: 'axis',
      ...sanitizedConfig.tooltip,
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e2e8f0',
      textStyle: {
        color: '#0f172a'
      }
    }
  };

  return (
    <div className="px-6" data-testid="chart-widget-message">
      <div className="flex gap-3 mb-6 items-start">
        {/* We place it in the same flex layout as ChatMessage */}
        <div className="flex-1 min-w-0">
          <Card className="w-full bg-card border-primary/30 shadow-sm">
            <CardContent className="p-4 relative">
              <div className="flex items-center justify-between gap-2 mb-4">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-primary" />
                  <span className="text-sm font-semibold text-primary">Data Visualization</span>
                </div>
                
                <div className="relative">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="h-8 flex items-center gap-1 text-xs"
                    onClick={() => setShowDashboards(!showDashboards)}
                  >
                    <Pin className="w-3 h-3" /> Pin
                  </Button>
                  
                  {showDashboards && (
                    <div className="absolute right-0 top-10 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg border border-gray-200 dark:border-gray-700 z-50 overflow-hidden">
                      <div className="text-xs font-medium text-gray-500 px-3 py-2 border-b border-gray-100 dark:border-gray-700">
                        Chọn Dashboard
                      </div>
                      <div className="max-h-48 overflow-y-auto">
                        {dashboards.length === 0 ? (
                          <div className="px-3 py-2 text-xs text-gray-400">Chưa có Dashboard nào</div>
                        ) : (
                          dashboards.map(db => (
                            <button
                              key={db.id}
                              disabled={pinning}
                              onClick={() => handlePin(db.id)}
                              className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                            >
                              {db.name}
                            </button>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <div className="h-[400px] w-full">
                <ReactECharts 
                  option={enhancedConfig} 
                  style={{ height: '100%', width: '100%' }}
                  theme="light"
                  opts={{ renderer: 'canvas' }}
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ChartWidget;
