import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Card, CardContent } from '@/components/ui/card';
import { BarChart3 } from 'lucide-react';

interface ChartWidgetProps {
  chartConfig: any;
}

const ChartWidget: React.FC<ChartWidgetProps> = ({ chartConfig }) => {
  if (!chartConfig) return null;

  // Enhance the chart config with a modern corporate theme
  const enhancedConfig = {
    ...chartConfig,
    backgroundColor: 'transparent',
    textStyle: {
      fontFamily: 'Inter, sans-serif'
    },
    tooltip: {
      trigger: 'axis',
      ...chartConfig.tooltip,
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
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="w-4 h-4 text-primary" />
                <span className="text-sm font-semibold text-primary">Data Visualization</span>
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
