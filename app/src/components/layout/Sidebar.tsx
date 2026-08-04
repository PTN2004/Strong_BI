import React from 'react';
import { useIsMobile } from '@/hooks/use-mobile';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import {
  PanelLeft,
  BookOpen,
  LifeBuoy,
  Waypoints,
  Sliders,
  Menu,
  MessageSquare
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from "@/lib/utils";
import ThemeToggle from '@/components/ui/theme-toggle';

interface SidebarProps {
  className?: string;
  onSchemaClick?: () => void;
  isSchemaOpen?: boolean;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  onSettingsClick?: () => void;
}

const SidebarIcon = ({ icon: Icon, label, active, onClick, href, testId, isCollapsed }: {
  icon: React.ElementType,
  label: string,
  active?: boolean,
  onClick?: () => void,
  href?: string,
  testId?: string,
  isCollapsed?: boolean
}) => {
  const content = (
    <div className={cn(
      "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 overflow-hidden",
      active 
        ? 'bg-primary/10 text-primary font-medium' 
        : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      isCollapsed ? 'justify-center' : 'justify-start'
    )}>
      <Icon className="h-5 w-5 flex-shrink-0" />
      {!isCollapsed && <span className="text-sm whitespace-nowrap">{label}</span>}
    </div>
  );

  const wrapperProps = {
    'data-testid': testId,
    onClick,
    className: "w-full focus:outline-none"
  };

  const interactiveElement = onClick ? (
    <button {...wrapperProps}>{content}</button>
  ) : href ? (
    <a href={href} target="_blank" rel="noopener noreferrer" {...wrapperProps}>{content}</a>
  ) : (
    <Link to="#" {...wrapperProps}>{content}</Link>
  );

  if (!isCollapsed) return interactiveElement;

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          {interactiveElement}
        </TooltipTrigger>
        <TooltipContent side="right" className="bg-popover text-popover-foreground border-border/50 shadow-sm">
          {label}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

const Sidebar = ({ className, onSchemaClick, isSchemaOpen, isCollapsed = false, onToggleCollapse, onSettingsClick }: SidebarProps) => {
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const location = useLocation();
  
  const isSettingsOpen = location.pathname === '/settings';
  
  const handleSettingsClick = () => {
    if (onSettingsClick) {
      onSettingsClick();
    }
    if (isSettingsOpen) {
      navigate('/');
    } else {
      navigate('/settings');
    }
  };

  return (
    <aside className={cn(
      "flex flex-col bg-transparent transition-all duration-300",
      className
    )}>
      {/* Header section with toggle and logo */}
      <div className="h-20 flex items-center px-4 gap-3">
        <button
          onClick={onToggleCollapse}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-card text-foreground hover:bg-muted/80 shadow-sm transition-all"
          title="Toggle Sidebar"
          data-testid="sidebar-toggle"
        >
          <Menu className="h-5 w-5" />
        </button>
        
        {!isCollapsed && (
          <div className="flex items-center gap-2 overflow-hidden animate-in fade-in zoom-in duration-300">
            <div className="bg-primary text-primary-foreground font-bold text-sm px-1.5 py-0.5 rounded">LDK</div>
            <span className="font-semibold text-primary whitespace-nowrap">StrongBI</span>
          </div>
        )}
      </div>

      <nav className="flex flex-col gap-2 px-3 py-4 flex-1">
        <SidebarIcon
          icon={MessageSquare}
          label="Dashboard"
          active={location.pathname === '/'}
          onClick={() => navigate('/')}
          isCollapsed={isCollapsed}
          testId="dashboard-link"
        />
        <SidebarIcon
          icon={Waypoints}
          label="Schema Viewer"
          active={isSchemaOpen}
          onClick={onSchemaClick}
          isCollapsed={isCollapsed}
          testId="schema-button"
        />
      </nav>
      
      <div className="flex justify-center my-2 opacity-30">
        <div className="w-8 h-px bg-current"></div>
      </div>
      
      <nav className="flex flex-col gap-2 px-3 pb-6">
        <div className="flex items-center justify-center mb-2">
           <ThemeToggle />
        </div>
        <SidebarIcon 
          icon={Sliders} 
          label="Settings" 
          active={isSettingsOpen} 
          onClick={handleSettingsClick} 
          isCollapsed={isCollapsed} 
          testId="settings-button" 
        />
        <SidebarIcon 
          icon={BookOpen} 
          label="Documentation" 
          href="https://docs.falkordb.com/" 
          isCollapsed={isCollapsed} 
          testId="documentation-link" 
        />
        <SidebarIcon 
          icon={LifeBuoy} 
          label="Support" 
          href="https://discord.com/invite/jyUgBweNQz" 
          isCollapsed={isCollapsed} 
          testId="support-link" 
        />
      </nav>
    </aside>
  );
};

export default Sidebar;