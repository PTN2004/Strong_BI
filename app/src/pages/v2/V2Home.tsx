import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Sparkles, Database, ArrowRight, Zap, BarChart3, LogIn } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import LoginModal from '@/components/modals/LoginModal';

const BentoCard = ({ title, description, icon: Icon, onClick, className }: any) => (
  <div 
    onClick={onClick}
    className={cn(
      "group cursor-pointer rounded-2xl p-5 transition-all duration-300",
      "bg-card border border-border/50 hover:border-primary/40",
      "shadow-sm hover:shadow-md",
      className
    )}
  >
    <div className="flex justify-between items-start mb-3">
      <div className="p-2 rounded-lg bg-primary/10 text-primary">
        <Icon className="w-4 h-4" />
      </div>
      <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 -translate-x-2 transition-all group-hover:opacity-100 group-hover:translate-x-0" />
    </div>
    <h3 className="text-sm font-semibold text-foreground mb-1">{title}</h3>
    <p className="text-xs text-muted-foreground line-clamp-2">{description}</p>
  </div>
);

const V2Home = () => {
  const [query, setQuery] = useState('');
  const [showLoginModal, setShowLoginModal] = useState(false);
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/workspace?q=${encodeURIComponent(query)}`);
    }
  };

  const suggestions = [
    "Show me the top 5 customers by total revenue this year",
    "What is the average order value across different regions?",
    "Which products have stock levels below 20 units?"
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 h-full min-h-[600px] relative bg-background">
      
      {/* Top Header Bar for Sign In (Fallback if needed, though Layout handles most of this now. Keeping login for unauth users) */}
      {!isAuthenticated && (
        <div className="absolute top-4 right-6 flex items-center justify-between z-20">
          <Button 
            variant="outline" 
            onClick={() => setShowLoginModal(true)}
            className="rounded-lg px-4 h-9 text-xs font-bold border-border hover:bg-muted"
          >
            <LogIn className="w-3.5 h-3.5 mr-1.5" />
            Sign In
          </Button>
        </div>
      )}

      {/* Central Command Area */}
      <div className="w-full max-w-3xl space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 mt-4">
        
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-semibold mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Data Assistant</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold text-foreground tracking-tight">
            Ask your data <span className="text-primary">anything</span>.
          </h1>
          <p className="text-sm md:text-base text-muted-foreground max-w-xl mx-auto">
            Get instant SQL queries, charts, and insights in plain English. No code required.
          </p>
        </div>

        {/* Massive Search Prompt */}
        <form onSubmit={handleSearch} className="relative group mt-8">
          <div className="relative flex items-center bg-card border border-border shadow-sm hover:shadow-md rounded-2xl p-1.5 transition-all duration-300 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
            <div className="pl-4 pr-2 text-muted-foreground group-focus-within:text-primary transition-colors">
              <Search className="w-5 h-5" />
            </div>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Show me the revenue trend for the last 6 months..."
              className="flex-1 bg-transparent border-none outline-none text-base md:text-lg text-foreground placeholder:text-muted-foreground/50 py-3"
            />
            <Button 
              type="submit" 
              size="lg" 
              className="rounded-xl px-6 h-12 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold ml-2"
              disabled={!query.trim()}
            >
              Analyze
            </Button>
          </div>
        </form>

      </div>

      {/* Bento Box Suggestions Grid */}
      <div className="w-full max-w-4xl mt-16 grid grid-cols-1 md:grid-cols-3 gap-4 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-150 fill-mode-both">
        <BentoCard 
          title="Top Customers"
          description="Who are the top 5 customers by total revenue this year?"
          icon={Zap}
          onClick={() => setQuery(suggestions[0])}
        />
        <BentoCard 
          title="Regional AOV"
          description="What is the average order value across different regions?"
          icon={Database}
          onClick={() => setQuery(suggestions[1])}
        />
        <BentoCard 
          title="Low Inventory"
          description="Which products have stock levels below 20 units?"
          icon={BarChart3}
          onClick={() => setQuery(suggestions[2])}
        />
      </div>

      {/* Login Modal */}
      <LoginModal open={showLoginModal} onOpenChange={setShowLoginModal} />

    </div>
  );
};

export default V2Home;
