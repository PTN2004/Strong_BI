import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send } from "lucide-react";

interface QueryInputProps {
  onSubmit: (query: string, version?: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";

const QueryInput = ({ onSubmit, placeholder = "Ask me anything about your database...", disabled = false }: QueryInputProps) => {
  const [query, setQuery] = useState('');
  const [engineVersion, setEngineVersion] = useState<'v4' | 'v5'>('v4');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !disabled) {
      onSubmit(query.trim(), engineVersion);
      setQuery('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative group mx-auto w-full max-w-4xl animate-slide-up" data-testid="query-input-form">
      <div className="relative flex items-end bg-card/90 backdrop-blur-xl rounded-[2rem] border border-border shadow-md transition-all duration-500 focus-within:shadow-lg focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20 overflow-hidden hover:border-primary/30">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-transparent to-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
        <Textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="min-h-[60px] max-h-[200px] w-full bg-transparent border-0 text-foreground placeholder:text-muted-foreground resize-none py-5 pl-8 pr-40 focus-visible:ring-0 focus-visible:ring-offset-0 disabled:opacity-50 text-base leading-relaxed relative z-10 scrollbar-hide"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !disabled) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          data-testid="query-textarea"
        />
        
        <div className="absolute right-16 bottom-3.5 z-10 hidden sm:block">
          <Popover>
            <PopoverTrigger asChild>
              <button
                type="button"
                disabled={disabled}
                className="flex items-center gap-1.5 bg-transparent hover:bg-muted text-muted-foreground px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors outline-none disabled:opacity-50"
              >
                <span>{engineVersion === 'v4' ? 'Model V4' : 'Model V5'}</span>
                <svg className="w-3 h-3 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" /></svg>
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-[320px] p-2 rounded-2xl mb-2 mr-4 shadow-xl border border-border" side="top" align="end" sideOffset={10}>
              <div className="flex flex-col gap-1">
                <div className="px-2 py-2 mb-1 border-b border-border/50 flex justify-between items-center">
                  <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Phiên bản phân tích</p>
                  <a href="/docs" target="_blank" rel="noopener noreferrer" className="text-[10px] text-primary hover:underline">Docs &rarr;</a>
                </div>

                <button
                  type="button"
                  onClick={() => setEngineVersion('v4')}
                  className={cn(
                    "flex flex-col items-start gap-1 p-3 rounded-xl text-left transition-colors w-full",
                    engineVersion === 'v4' ? "bg-primary/10 border border-primary/20" : "hover:bg-muted border border-transparent"
                  )}
                >
                  <div className="flex items-center justify-between w-full">
                    <span className={cn("font-bold text-sm", engineVersion === 'v4' ? "text-primary" : "text-foreground")}>Model V4 (Flash)</span>
                    {engineVersion === 'v4' && <CheckCircle2 className="w-4 h-4 text-primary" />}
                  </div>
                  <span className="text-xs text-muted-foreground leading-relaxed mt-1">Phiên bản tối ưu tốc độ. Truy vấn trực tiếp vào dữ liệu để cho ra kết quả siêu tốc. Phù hợp xem nhanh số liệu.</span>
                </button>

                <button
                  type="button"
                  onClick={() => setEngineVersion('v5')}
                  className={cn(
                    "flex flex-col items-start gap-1 p-3 rounded-xl text-left transition-colors w-full",
                    engineVersion === 'v5' ? "bg-primary/10 border border-primary/20" : "hover:bg-muted border border-transparent"
                  )}
                >
                  <div className="flex items-center justify-between w-full">
                    <span className={cn("font-bold text-sm", engineVersion === 'v5' ? "text-primary" : "text-foreground")}>Model V5 (Beta)</span>
                    {engineVersion === 'v5' && <CheckCircle2 className="w-4 h-4 text-primary" />}
                  </div>
                  <span className="text-xs text-muted-foreground leading-relaxed mt-1">Phiên bản phân tích ngữ nghĩa đa bước chuyên sâu, trả về nhiều nội dung và đồ thị. Phù hợp cho báo cáo phức tạp.</span>
                </button>
              </div>
            </PopoverContent>
          </Popover>
        </div>

        <Button
          type="submit"
          size="icon"
          className="absolute right-3 bottom-3 h-11 w-11 rounded-full bg-primary hover:bg-primary/90 text-primary-foreground shadow-md transition-all duration-300 hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 z-10 hover:shadow-[0_0_20px_-5px_rgba(var(--primary),0.5)]"
          disabled={!query.trim() || disabled}
          aria-label="Send query"
          data-testid="send-query-btn"
        >
          <Send className="w-5 h-5 ml-0.5" />
        </Button>
      </div>
    </form>
  );
};

export default QueryInput;
