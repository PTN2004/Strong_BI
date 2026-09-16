import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Home, MessageSquare, Database, LogOut, Settings, ChevronLeft, ChevronRight, Zap, History } from 'lucide-react';
import { cn } from '@/lib/utils';
import ThemeToggle from '@/components/ui/theme-toggle';
import { useAuth } from '@/contexts/AuthContext';
import { useDatabase } from '@/contexts/DatabaseContext';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';

interface V2LayoutProps {
  children: React.ReactNode;
}

const SidebarItem = ({ icon: Icon, label, isActive, isCollapsed, onClick }: any) => (
  <button
    onClick={onClick}
    title={isCollapsed ? label : undefined}
    className={cn(
      "flex items-center gap-3 w-full px-3 py-2.5 rounded-lg transition-all duration-200",
      isActive 
        ? "bg-primary text-primary-foreground font-semibold shadow-sm" 
        : "text-muted-foreground hover:bg-muted hover:text-foreground font-medium"
    )}
  >
    <Icon className="w-5 h-5 flex-shrink-0" />
    {!isCollapsed && <span className="text-sm truncate">{label}</span>}
  </button>
);

const V2Layout = ({ children }: V2LayoutProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, isAuthenticated } = useAuth();
  const { selectedGraph } = useDatabase();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const isHome = location.pathname === '/' || location.pathname === '/v2/home';
  const isWorkspace = location.pathname.startsWith('/workspace');
  const isDatabases = location.pathname.startsWith('/databases');
  const isSettings = location.pathname.startsWith('/settings');
  const isConversations = location.pathname.startsWith('/conversations');

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
      navigate('/');
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoggingOut(false);
    }
  };

  const getInitials = (name?: string) => {
    if (!name) return 'U';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  const getRoleBadge = (role?: string) => {
    switch (role?.toLowerCase()) {
      case 'admin':
        return <Badge className="bg-rose-100 text-rose-700 hover:bg-rose-100 border-none px-2 py-0.5 rounded-full font-semibold text-[10px]">Admin</Badge>;
      case 'analyst':
        return <Badge className="bg-sky-100 text-sky-700 hover:bg-sky-100 border-none px-2 py-0.5 rounded-full font-semibold text-[10px]">Analyst</Badge>;
      default:
        return <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 border-none px-2 py-0.5 rounded-full font-semibold text-[10px]">Viewer</Badge>;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      
      {/* Sidebar */}
      <aside className={cn(
        "flex flex-col bg-card border-r border-border transition-all duration-300 relative z-20 shadow-sm",
        isSidebarCollapsed ? "w-[72px]" : "w-[240px]"
      )}>
        {/* Logo Area */}
        <div className="h-14 flex items-center px-4 border-b border-border/50">
          <div className="flex items-center gap-2 overflow-hidden">
            <Zap className="w-6 h-6 text-primary flex-shrink-0" />
            {!isSidebarCollapsed && <span className="font-bold text-sm tracking-tight whitespace-nowrap">LDK StrongBI</span>}
          </div>
        </div>

        {/* Toggle Button */}
        <button 
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          className="absolute -right-3 top-16 bg-card border border-border rounded-full p-1 text-muted-foreground hover:text-primary hover:bg-muted shadow-sm z-30"
        >
          {isSidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>

        {/* Navigation Links */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          <SidebarItem icon={Home} label="Home" isActive={isHome} isCollapsed={isSidebarCollapsed} onClick={() => navigate('/')} />
          <SidebarItem icon={MessageSquare} label="Workspace" isActive={isWorkspace} isCollapsed={isSidebarCollapsed} onClick={() => navigate('/workspace')} />
          <SidebarItem icon={Database} label="Data Sources" isActive={isDatabases} isCollapsed={isSidebarCollapsed} onClick={() => navigate('/databases')} />
          <SidebarItem icon={History} label="Lịch sử hội thoại" isActive={isConversations} isCollapsed={isSidebarCollapsed} onClick={() => navigate('/conversations')} />
        </nav>

        {/* Bottom Actions */}
        <div className="p-3 border-t border-border/50 space-y-2">
          <SidebarItem icon={Settings} label="Settings" isActive={isSettings} isCollapsed={isSidebarCollapsed} onClick={() => navigate('/settings')} />
          
          <div className="flex justify-center w-full py-1">
            <ThemeToggle />
          </div>

          {isAuthenticated && user && (
            <div className="pt-2 flex justify-center w-full border-t border-border/30">
              <Popover>
                <PopoverTrigger asChild>
                  <button className="flex items-center gap-2 w-full p-1.5 rounded-lg hover:bg-muted transition-all">
                    <Avatar className="w-8 h-8 flex-shrink-0 border border-border shadow-sm">
                      <AvatarFallback className="bg-primary/10 text-primary text-xs font-bold">
                        {getInitials(user.name)}
                      </AvatarFallback>
                    </Avatar>
                    {!isSidebarCollapsed && (
                      <div className="flex flex-col items-start min-w-0 flex-1 overflow-hidden">
                        <span className="text-xs font-semibold truncate w-full text-left">{user.name}</span>
                        {getRoleBadge(user.role)}
                      </div>
                    )}
                  </button>
                </PopoverTrigger>
                <PopoverContent side="right" align="end" className="w-64 bg-card border border-border shadow-lg rounded-xl p-4 ml-2 mb-2">
                  <div className="space-y-4">
                    <div className="flex items-center gap-3">
                      <Avatar className="w-10 h-10 border border-border">
                        <AvatarFallback className="bg-primary text-primary-foreground font-bold">
                          {getInitials(user.name)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex flex-col items-start min-w-0">
                        <h4 className="font-semibold text-sm truncate w-full text-left">{user.name}</h4>
                        <p className="text-xs text-muted-foreground truncate w-full text-left mb-1">{user.email}</p>
                        {getRoleBadge(user.role)}
                      </div>
                    </div>
                    <div className="h-px bg-border/50" />
                    <Button 
                      variant="ghost" 
                      className="w-full justify-start text-destructive hover:text-destructive hover:bg-destructive/10 rounded-lg h-9"
                      onClick={handleLogout}
                      disabled={isLoggingOut}
                    >
                      <LogOut className="w-4 h-4 mr-2" />
                      Sign Out
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 relative bg-background">
        {/* Top Header */}
        <header className="h-14 flex items-center justify-between px-4 border-b border-border/50 bg-card z-10 shrink-0 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-foreground capitalize">
              {isHome ? 'Home' : location.pathname.split('/')[1] || 'Dashboard'}
            </span>
          </div>

          {/* Active Database Context */}
          <div className="flex items-center">
            {selectedGraph ? (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-success/10 border border-success/20">
                <Database className="w-3.5 h-3.5 text-success" />
                <span className="text-xs font-semibold text-success flex items-center gap-1.5">
                  Connected: <span className="text-foreground">{selectedGraph.name}</span>
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-warning/10 border border-warning/20 cursor-pointer hover:bg-warning/20 transition-colors" onClick={() => navigate('/databases')}>
                <Database className="w-3.5 h-3.5 text-warning" />
                <span className="text-xs font-semibold text-warning">No Database Selected</span>
              </div>
            )}
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-auto relative">
          {children}
        </div>
      </main>
    </div>
  );
};

export default V2Layout;
