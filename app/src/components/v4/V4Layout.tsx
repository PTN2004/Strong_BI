import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Database, Settings, LogOut, ChevronLeft, ChevronRight, Home, MessageSquare, Cpu, Moon, Sun } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { useDatabase } from '@/contexts/DatabaseContext';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import ThemeToggle from '@/components/ui/theme-toggle';

interface V4LayoutProps {
  children: React.ReactNode;
}

const SidebarItem = ({ icon: Icon, label, isActive, isCollapsed, onClick }: any) => (
  <button
    onClick={onClick}
    title={isCollapsed ? label : undefined}
    className={cn(
      "flex items-center gap-3 w-full px-4 py-3 transition-all duration-200 group",
      isActive 
        ? "bg-[#2563eb] text-white font-semibold rounded-[16px] shadow-sm" 
        : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800/50 hover:text-gray-900 dark:hover:text-gray-100 font-medium rounded-[16px]"
    )}
  >
    <Icon className={cn("w-[18px] h-[18px] flex-shrink-0 transition-transform group-hover:scale-105", isActive ? "text-white" : "")} />
    {!isCollapsed && <span className="text-sm truncate">{label}</span>}
  </button>
);

const V4Layout = ({ children }: V4LayoutProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { selectedGraph } = useDatabase();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const isHome = location.pathname === '/v2/home' || location.pathname === '/'; // Assuming home mapping
  const isWorkspace = location.pathname === '/workspace';
  const isChat = location.pathname.startsWith('/v4/dashboard');
  const isDatabases = location.pathname.startsWith('/databases');
  const isSettings = location.pathname.startsWith('/settings');

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

  // Determine Page Title for Top Header
  let pageTitle = "V4";
  if (isDatabases) pageTitle = "Databases";
  else if (isSettings) pageTitle = "Settings";
  else if (isWorkspace) pageTitle = "Workspace";

  return (
    <div className="flex h-screen overflow-hidden bg-[#f4f7fc] dark:bg-[#09090b] text-foreground font-sans">
      
      {/* V4 Sidebar */}
      <aside className={cn(
        "flex flex-col bg-[#f8f9fc] dark:bg-[#020817] border-r border-gray-200 dark:border-gray-800 transition-all duration-300 relative z-20 shrink-0",
        isSidebarCollapsed ? "w-[76px]" : "w-[240px]"
      )}>
        {/* Logo Area */}
        <div className="h-16 flex items-center px-5 shrink-0">
          <div className="flex items-center gap-3 overflow-hidden cursor-pointer hover:opacity-80 transition-opacity" onClick={() => navigate('/v4/dashboard')}>
            <Cpu className="w-6 h-6 text-[#2563eb] flex-shrink-0" />
            {!isSidebarCollapsed && (
              <span className="font-bold text-[15px] tracking-tight text-[#1e293b] dark:text-white">LDK StrongBI</span>
            )}
          </div>
        </div>

        {/* Toggle Button */}
        <button 
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          className="absolute -right-3 top-[72px] bg-white dark:bg-[#020817] border border-gray-200 dark:border-gray-800 rounded-full p-1 text-gray-400 hover:text-[#2563eb] hover:border-[#2563eb] shadow-sm z-30 transition-all"
        >
          {isSidebarCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
        </button>

        {/* Navigation Links */}
        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          <SidebarItem icon={Home} label="Home" isActive={isHome} isCollapsed={isSidebarCollapsed} onClick={() => navigate('/')} />
          <SidebarItem icon={MessageSquare} label="Workspace" isActive={isWorkspace} isCollapsed={isSidebarCollapsed} onClick={() => navigate('/workspace')} />
          <SidebarItem icon={Cpu} label="V4 Dashboard" isActive={isChat} isCollapsed={isSidebarCollapsed} onClick={() => navigate('/v4/dashboard')} />
          <SidebarItem icon={Database} label="Data Sources" isActive={isDatabases} isCollapsed={isSidebarCollapsed} onClick={() => navigate('/databases')} />
        </nav>

        {/* Bottom Area */}
        <div className="p-3 border-t border-gray-200 dark:border-gray-800 space-y-4 shrink-0">
          <SidebarItem icon={Settings} label="Settings" isActive={isSettings} isCollapsed={isSidebarCollapsed} onClick={() => navigate('/settings')} />
          
          <div className="flex items-center justify-center pt-2">
            <ThemeToggle />
          </div>

          {user && (
            <div className="pt-2 px-1">
              <Popover>
                <PopoverTrigger asChild>
                  <button className="flex items-center gap-3 w-full p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group">
                    <Avatar className="w-9 h-9 flex-shrink-0 bg-gray-200 text-gray-600 text-sm font-semibold">
                      <AvatarFallback className="bg-gray-200 text-gray-700">{getInitials(user.firstName || user.email)}</AvatarFallback>
                    </Avatar>
                    {!isSidebarCollapsed && (
                      <div className="flex flex-col items-start overflow-hidden text-left flex-1">
                        <span className="text-sm font-semibold text-gray-700 dark:text-gray-200 truncate w-full">{user.firstName} {user.lastName}</span>
                        <span className="text-[10px] font-bold text-red-500 bg-red-50 dark:bg-red-500/10 px-1.5 py-0.5 rounded-md uppercase tracking-wider">{user.role}</span>
                      </div>
                    )}
                  </button>
                </PopoverTrigger>
                <PopoverContent className="w-56 p-2 rounded-xl" side="right" align="end" sideOffset={20}>
                  <div className="flex flex-col space-y-1">
                    <div className="px-2 py-2 border-b border-border mb-1">
                      <p className="text-sm font-medium">{user.firstName} {user.lastName}</p>
                      <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                    </div>
                    <Button variant="ghost" className="w-full justify-start text-red-600 hover:text-red-700 hover:bg-red-50" onClick={handleLogout} disabled={isLoggingOut}>
                      <LogOut className="w-4 h-4 mr-2" />
                      {isLoggingOut ? "Logging out..." : "Log out"}
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col relative min-w-0 overflow-hidden bg-white dark:bg-black/20 m-3 rounded-[24px] shadow-sm border border-gray-100 dark:border-gray-800">
        
        {/* Top Header */}
        <header className="h-14 flex items-center justify-between px-6 border-b border-gray-100 dark:border-gray-800 shrink-0">
          <h2 className="text-sm font-bold text-[#1e293b] dark:text-gray-200">{pageTitle}</h2>
          
          {selectedGraph ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
              <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0 animate-pulse"></span>
              Connected: {selectedGraph.name}
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50 text-gray-500 text-xs font-semibold">
              <span className="w-2 h-2 rounded-full bg-gray-400 flex-shrink-0"></span>
              No Database Connected
            </div>
          )}
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-hidden relative">
          {children}
        </div>
      </main>

    </div>
  );
};

export default V4Layout;
