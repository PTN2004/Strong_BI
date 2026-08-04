import React from 'react';
import Sidebar from './Sidebar';
import { useLocation } from 'react-router-dom';
import { useIsMobile } from '@/hooks/use-mobile';
import { cn } from '@/lib/utils';

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout = ({ children }: MainLayoutProps) => {
  const isMobile = useIsMobile();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = React.useState(false);

  return (
    <div className="flex h-screen bg-secondary/20 text-foreground overflow-hidden">
      {/* Sidebar - Borderless, integrated */}
      <Sidebar 
        isCollapsed={isSidebarCollapsed} 
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)} 
        className={cn(
          "fixed top-0 left-0 h-full transition-all duration-300 z-50",
          isSidebarCollapsed ? "w-[80px]" : "w-[260px]"
        )}
      />
      
      {/* Main Content Area - Floating Card Style */}
      <div className={cn(
        "flex-1 flex flex-col transition-all duration-300",
        isMobile ? "ml-[80px] p-2" : (isSidebarCollapsed ? "ml-[80px] p-4" : "ml-[260px] p-4")
      )}>
        <div className="flex-1 bg-card shadow-sm border border-primary/5 rounded-2xl overflow-hidden flex flex-col relative">
          {children}
        </div>
      </div>
    </div>
  );
};

export default MainLayout;
