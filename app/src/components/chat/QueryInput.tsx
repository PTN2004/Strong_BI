import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send } from "lucide-react";

interface QueryInputProps {
  onSubmit: (query: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

const QueryInput = ({ onSubmit, placeholder = "Ask me anything about your database...", disabled = false }: QueryInputProps) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !disabled) {
      onSubmit(query.trim());
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
          className="min-h-[60px] max-h-[200px] w-full bg-transparent border-0 text-foreground placeholder:text-muted-foreground resize-none py-5 pl-8 pr-16 focus-visible:ring-0 focus-visible:ring-offset-0 disabled:opacity-50 text-base leading-relaxed relative z-10 scrollbar-hide"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !disabled) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          data-testid="query-textarea"
        />
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
