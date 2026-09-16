import React, { useState } from 'react';
import { Database, Search, Code, MessageSquare, AlertTriangle, Copy, Check, ChevronDown, ChevronRight, BrainCircuit } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import type { User as UserType } from '@/types/api';
import ChartWidget from './ChartWidget';

interface Step {
  icon: 'search' | 'database' | 'code' | 'message';
  text: string;
}

interface ChatMessageProps {
  type: 'user' | 'ai' | 'ai-steps' | 'sql-query' | 'query-result' | 'confirmation' | 'chart-config';
  content: string;
  steps?: Step[];
  queryData?: any[]; // For table data
  chartConfig?: any; // For ECharts options
  analysisInfo?: {
    confidence?: number;
    missing?: string;
    ambiguities?: string;
    explanation?: string;
    isValid?: boolean;
  };
  confirmationData?: {
    sqlQuery: string;
    operationType: string;
    message: string;
  };
  metrics?: {
    total_tokens: number;
    cost_usd: number;
    api_calls_count: number;
    engine_version: string;
  };
  progress?: number; // Progress percentage for AI steps
  user?: UserType | null; // User info for avatar
  onConfirm?: () => void;
  onCancel?: () => void;
}

const ChatMessage = ({ type, content, steps, queryData, chartConfig, analysisInfo, confirmationData, metrics, progress, user, onConfirm, onCancel }: ChatMessageProps) => {
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const handleCopyQuery = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  if (type === 'confirmation') {
    const operationType = (confirmationData?.operationType ?? 'UNKNOWN').toUpperCase();
    const isHighRisk = ['DELETE', 'DROP', 'TRUNCATE'].includes(operationType);

    return (
      <div className="px-6" data-testid="confirmation-message">
        <div className="flex gap-3 mb-6 items-start">
          <Avatar className="w-8 h-8 flex-shrink-0 shadow-sm border border-primary/20">
            <AvatarFallback className="bg-primary text-primary-foreground text-xs font-bold">
              BI
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <Card className={`${isHighRisk ? 'border-error/50 bg-error/5' : 'border-warning/50 bg-warning/5'}`}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <AlertTriangle className={`w-5 h-5 ${isHighRisk ? 'text-error' : 'text-warning'}`} />
                  <span className={`text-base font-semibold ${isHighRisk ? 'text-error' : 'text-warning'}`}>
                    Destructive Operation Detected
                  </span>
                </div>

                <div className="space-y-3">
                  <div>
                    <p className="text-foreground text-sm mb-2">
                      This operation will perform a <span className={`font-semibold ${isHighRisk ? 'text-error' : 'text-warning'}`}>{operationType}</span> query:
                    </p>
                    {confirmationData?.sqlQuery && (
                      <div className="bg-background border border-border rounded p-3 overflow-x-auto">
                        <pre className="text-sm font-mono text-foreground whitespace-pre-wrap break-words overflow-wrap-anywhere">
                          <code className="language-sql">{confirmationData.sqlQuery}</code>
                        </pre>
                      </div>
                    )}
                  </div>

                  <div className={`${isHighRisk ? 'bg-error/10 border-error/50' : 'bg-warning/10 border-warning/50'} border rounded p-3`}>
                    <p className="text-sm text-foreground">
                      {isHighRisk ? (
                        <>
                          <span className="font-semibold text-error">⚠️ WARNING:</span> This operation may be irreversible and will permanently modify your database.
                        </>
                      ) : (
                        <>This operation will make changes to your database. Please review carefully before confirming.</>
                      )}
                    </p>
                  </div>

                  <div className="flex gap-2 pt-2">
                    <Button
                      variant="outline"
                      onClick={onCancel}
                      className="flex-1 bg-card border-border text-muted-foreground hover:bg-muted"
                      data-testid="confirmation-cancel-button"
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={onConfirm}
                      className={`flex-1 ${isHighRisk ? 'bg-error hover:bg-error/90' : 'bg-warning hover:bg-warning/90'} text-white font-semibold`}
                      data-testid="confirmation-confirm-button"
                    >
                      Confirm {operationType}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (type === 'user') {
    return (
      <div className="px-6 animate-slide-in-right" data-testid="user-message">
        <div className="flex justify-end gap-3 mb-6">
          <div className="flex-1 max-w-xl">
            <Card className="bg-primary text-primary-foreground border-transparent shadow-lg inline-block float-right rounded-3xl rounded-tr-md backdrop-blur-sm">
              <CardContent className="p-4">
                <p className="text-[15px] leading-relaxed">{content}</p>
              </CardContent>
            </Card>
          </div>
          <Avatar className="h-10 w-10 border-2 border-background shadow-md flex-shrink-0">
            <AvatarImage src={user?.picture} alt={user?.name || user?.email} />
            <AvatarFallback className="bg-primary/20 text-primary font-medium">
              {(user?.name || user?.email || 'U').charAt(0).toUpperCase()}
            </AvatarFallback>
          </Avatar>
        </div>
      </div>
    );
  }

  if (type === 'sql-query') {
    return null;
  }

  if (type === 'query-result') {
    return null;
  }

  if (type === 'ai') {
    return (
      <div className="px-6 animate-fade-in" data-testid="ai-message">
        <div className="flex gap-4 mb-6 items-start">
          <Avatar className="w-10 h-10 flex-shrink-0 shadow-md border-2 border-background bg-gradient-to-br from-primary/20 to-primary/10">
              <AvatarFallback className="bg-transparent text-primary text-xs font-bold">
                BI
              </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <Card className="glass-card inline-block rounded-3xl rounded-tl-md">
              <CardContent className="p-5 text-foreground text-[15px] leading-relaxed prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {content}
                </ReactMarkdown>
                {metrics && (
                  <div className="mt-4 pt-3 border-t border-border/50 flex flex-wrap gap-2 text-xs text-muted-foreground select-none">
                    <div className="flex items-center gap-1.5 bg-muted/30 px-2.5 py-1 rounded-md border border-border/50">
                      <span className="font-medium">Model:</span>
                      <span className="text-primary font-semibold uppercase">{metrics.engine_version}</span>
                    </div>
                    <div className="flex items-center gap-1.5 bg-muted/30 px-2.5 py-1 rounded-md border border-border/50">
                      <span className="font-medium">API Calls:</span>
                      <span>{metrics.api_calls_count}</span>
                    </div>
                    <div className="flex items-center gap-1.5 bg-muted/30 px-2.5 py-1 rounded-md border border-border/50">
                      <span className="font-medium">Tokens:</span>
                      <span>{metrics.total_tokens.toLocaleString()}</span>
                    </div>
                    <div className="flex items-center gap-1.5 bg-muted/30 px-2.5 py-1 rounded-md border border-border/50">
                      <span className="font-medium">Cost:</span>
                      <span className="text-emerald-500/90 font-medium">${metrics.cost_usd.toFixed(4)}</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (type === 'ai-steps') {
    return (
      <div className="px-6 animate-fade-in" data-testid="ai-steps-message">
        <div className="flex gap-4 mb-6 items-start">
          <Avatar className="w-10 h-10 flex-shrink-0 shadow-md border-2 border-background bg-gradient-to-br from-primary/20 to-primary/10">
            <AvatarFallback className="bg-transparent text-primary text-xs font-bold">
              BI
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <Card className="glass-card w-fit max-w-full rounded-2xl rounded-tl-md">
              <div 
                className="flex items-center justify-between gap-4 p-3 cursor-pointer select-none hover:bg-muted/30 transition-colors rounded-t-2xl"
                onClick={() => setIsExpanded(!isExpanded)}
              >
                <div className="flex items-center gap-2">
                  <BrainCircuit className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">Pipeline & Reasoning Steps</span>
                </div>
                {isExpanded ? <ChevronDown className="w-4 h-4 text-muted-foreground" /> : <ChevronRight className="w-4 h-4 text-muted-foreground" />}
              </div>
              {isExpanded && (
                <CardContent className="p-4 pt-0 border-t border-white/10">
                  <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono mt-3 break-words overflow-wrap-anywhere">
                    {content}
                  </pre>
                  {progress !== undefined && (
                    <div className="mt-4">
                      <Progress value={progress} className="h-1.5" />
                      <p className="text-[11px] text-muted-foreground mt-1.5">{progress}% complete</p>
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (type === 'chart-config') {
    return null;
  }

  return null;
};

export default ChatMessage;
