import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Database, Settings, LogOut, ChevronLeft, ChevronRight, MessageSquareText, Cpu, History, BookOpen, ChevronDown, Check, LayoutDashboard, Plus, Building2, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { useDatabase } from '@/contexts/DatabaseContext';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from '@/components/ui/use-toast';
import ThemeToggle from '@/components/ui/theme-toggle';

interface V4LayoutProps {
  children: React.ReactNode;
}

const SidebarItem = ({ icon: Icon, label, isActive, isCollapsed, onClick }: any) => (
  <button
    onClick={onClick}
    title={isCollapsed ? label : undefined}
    className={cn(
      "flex items-center gap-3 w-full px-3.5 py-2.5 transition-all duration-200 group rounded-xl",
      isActive 
        ? "bg-blue-600 text-white font-semibold shadow-sm" 
        : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800/60 hover:text-gray-900 dark:hover:text-gray-100 font-medium"
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
  const { workspaces, activeWorkspace, setActiveWorkspace, createWorkspace } = useWorkspace();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  // New Workspace state
  const [isCreatingWs, setIsCreatingWs] = useState(false);
  const [newWsName, setNewWsName] = useState('');
  const [newWsIndustry, setNewWsIndustry] = useState('');
  const [isSubmittingWs, setIsSubmittingWs] = useState(false);

  const isChat = location.pathname === '/' || location.pathname === '/chat' || location.pathname.startsWith('/v4/dashboard');
  const isDashboards = location.pathname.startsWith('/dashboards');
  const isDatabases = location.pathname.startsWith('/databases');
  const isConversations = location.pathname.startsWith('/conversations');
  const isSettings = location.pathname.startsWith('/settings');
  const isDocs = location.pathname.startsWith('/docs');

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

  const handleCreateWorkspaceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) {
      toast({ variant: 'destructive', title: 'Lỗi', description: 'Vui lòng nhập tên Workspace' });
      return;
    }
    try {
      setIsSubmittingWs(true);
      const ws = await createWorkspace(newWsName.trim(), newWsIndustry.trim() || undefined);
      setNewWsName('');
      setNewWsIndustry('');
      setIsCreatingWs(false);
      toast({
        title: 'Tạo Workspace thành công!',
        description: `Đã chuyển sang workspace: ${ws.name}`,
      });
      window.location.reload();
    } catch (err: any) {
      toast({
        variant: 'destructive',
        title: 'Tạo Workspace thất bại',
        description: err.message || 'Không thể tạo Workspace mới.',
      });
    } finally {
      setIsSubmittingWs(false);
    }
  };

  const getInitials = (name?: string) => {
    if (!name) return 'U';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  // Determine Page Title for Top Header
  let pageTitle = "Trợ lý AI & Phân tích";
  if (isDashboards) pageTitle = "Báo cáo & Dashboards";
  else if (isDatabases) pageTitle = "Nguồn dữ liệu & Schema";
  else if (isConversations) pageTitle = "Lịch sử truy vấn";
  else if (isSettings) pageTitle = "Cài đặt & Hồ sơ";
  else if (isDocs) pageTitle = "Tài liệu Hướng dẫn";

  return (
    <div className="flex h-screen overflow-hidden bg-[#f4f7fc] dark:bg-[#09090b] text-foreground font-sans">
      
      {/* V4 Sidebar */}
      <aside className={cn(
        "flex flex-col bg-[#f8f9fc] dark:bg-[#020817] border-r border-gray-200 dark:border-gray-800 transition-all duration-300 relative z-20 shrink-0",
        isSidebarCollapsed ? "w-[72px]" : "w-[240px]"
      )}>
        {/* Logo Area */}
        <div className="h-16 flex items-center px-4 shrink-0">
          <div className="flex items-center gap-3 overflow-hidden cursor-pointer hover:opacity-85 transition-opacity" onClick={() => navigate('/')}>
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm flex-shrink-0">
              <Cpu className="w-5 h-5" />
            </div>
            {!isSidebarCollapsed && (
              <span className="font-bold text-[16px] tracking-tight text-gray-900 dark:text-white">StrongBI Agent</span>
            )}
          </div>
        </div>

        {/* Toggle Button */}
        <button 
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          className="absolute -right-3 top-[68px] bg-white dark:bg-[#020817] border border-gray-200 dark:border-gray-800 rounded-full p-1 text-gray-400 hover:text-blue-600 hover:border-blue-600 shadow-sm z-30 transition-all"
        >
          {isSidebarCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
        </button>

        {/* Core Navigation Items (Streamlined & Clean) */}
        <nav className="flex-1 py-3 px-3 space-y-1.5 overflow-y-auto">
          <SidebarItem 
            icon={MessageSquareText} 
            label="Hỏi đáp AI" 
            isActive={isChat} 
            isCollapsed={isSidebarCollapsed} 
            onClick={() => navigate('/')} 
          />
          <SidebarItem 
            icon={LayoutDashboard} 
            label="Dashboards" 
            isActive={isDashboards} 
            isCollapsed={isSidebarCollapsed} 
            onClick={() => navigate('/dashboards')} 
          />
          <SidebarItem 
            icon={Database} 
            label="Nguồn dữ liệu" 
            isActive={isDatabases} 
            isCollapsed={isSidebarCollapsed} 
            onClick={() => navigate('/databases')} 
          />
          <SidebarItem 
            icon={History} 
            label="Lịch sử truy vấn" 
            isActive={isConversations} 
            isCollapsed={isSidebarCollapsed} 
            onClick={() => navigate('/conversations')} 
          />
        </nav>

        {/* Bottom Area */}
        <div className="p-3 border-t border-gray-200 dark:border-gray-800 space-y-1.5 shrink-0">
          <SidebarItem 
            icon={Settings} 
            label="Cài đặt" 
            isActive={isSettings} 
            isCollapsed={isSidebarCollapsed} 
            onClick={() => navigate('/settings')} 
          />
          <SidebarItem 
            icon={BookOpen} 
            label="Tài liệu" 
            isActive={isDocs} 
            isCollapsed={isSidebarCollapsed} 
            onClick={() => navigate('/docs')} 
          />
          
          <div className="flex items-center justify-center pt-2">
            <ThemeToggle />
          </div>

          {user && (
            <div className="pt-2 px-1">
              <Popover>
                <PopoverTrigger asChild>
                  <button className="flex items-center gap-3 w-full p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group">
                    <Avatar className="w-8 h-8 flex-shrink-0 bg-gray-200 text-gray-700 text-xs font-semibold">
                      <AvatarFallback className="bg-gray-200 text-gray-700">{getInitials(user.firstName || user.email)}</AvatarFallback>
                    </Avatar>
                    {!isSidebarCollapsed && (
                      <div className="flex flex-col items-start overflow-hidden text-left flex-1">
                        <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 truncate w-full">{user.firstName} {user.lastName}</span>
                        <span className="text-[10px] font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 px-1.5 py-0.5 rounded uppercase tracking-wider">{user.role}</span>
                      </div>
                    )}
                  </button>
                </PopoverTrigger>
                <PopoverContent className="w-56 p-2 rounded-xl" side="right" align="end" sideOffset={15}>
                  <div className="flex flex-col space-y-1">
                    <div className="px-2 py-2 border-b border-border mb-1">
                      <p className="text-sm font-medium">{user.firstName} {user.lastName}</p>
                      <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                    </div>
                    <Button variant="ghost" className="w-full justify-start text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30" onClick={handleLogout} disabled={isLoggingOut}>
                      <LogOut className="w-4 h-4 mr-2" />
                      {isLoggingOut ? "Đang đăng xuất..." : "Đăng xuất"}
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col relative min-w-0 overflow-hidden bg-white dark:bg-black/20 m-2.5 rounded-[20px] shadow-sm border border-gray-100 dark:border-gray-800">
        
        {/* Top Header */}
        <header className="h-14 flex items-center justify-between px-5 border-b border-gray-100 dark:border-gray-800 shrink-0">
          <div className="flex items-center gap-4">
            <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">{pageTitle}</h2>
            
            {/* Workspace Selector */}
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="h-7 gap-2 border-dashed bg-transparent rounded-full px-3 text-gray-600 dark:text-gray-300">
                  <Building2 className="w-3.5 h-3.5 text-blue-600" />
                  <span className="text-xs font-medium">{activeWorkspace ? activeWorkspace.name : "Chọn Workspace"}</span>
                  <ChevronDown className="w-3 h-3 text-gray-400" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-64 p-2 rounded-xl" align="start">
                <div className="px-2 py-1.5 text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">
                  Danh sách Workspace
                </div>
                
                <div className="space-y-0.5 max-h-48 overflow-y-auto mb-2">
                  {workspaces.map(ws => (
                    <Button
                      key={ws.id}
                      variant="ghost"
                      size="sm"
                      className={cn(
                        "w-full justify-start font-medium text-xs rounded-lg h-8",
                        activeWorkspace?.id === ws.id ? "bg-blue-600/10 text-blue-600 hover:bg-blue-600/20 font-semibold" : "hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300"
                      )}
                      onClick={() => {
                        setActiveWorkspace(ws);
                        window.location.reload();
                      }}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className="truncate">{ws.name}</span>
                        {activeWorkspace?.id === ws.id && <Check className="w-3.5 h-3.5 ml-2 flex-shrink-0 text-blue-600" />}
                      </div>
                    </Button>
                  ))}
                </div>

                {/* Create New Workspace Inline Form */}
                <div className="border-t border-gray-100 dark:border-gray-800 pt-2 mt-1">
                  {!isCreatingWs ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full justify-start text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-50 dark:hover:bg-blue-950/30 h-8 rounded-lg"
                      onClick={() => setIsCreatingWs(true)}
                    >
                      <Plus className="w-3.5 h-3.5 mr-1.5" />
                      Tạo Workspace mới
                    </Button>
                  ) : (
                    <form onSubmit={handleCreateWorkspaceSubmit} className="space-y-2 p-1 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                      <Input
                        placeholder="Tên Workspace (vd: Sales Team)"
                        value={newWsName}
                        onChange={(e) => setNewWsName(e.target.value)}
                        className="h-7 text-xs"
                        autoFocus
                      />
                      <Input
                        placeholder="Ngành nghề (vd: Bán lẻ, FMCG)"
                        value={newWsIndustry}
                        onChange={(e) => setNewWsIndustry(e.target.value)}
                        className="h-7 text-xs"
                      />
                      <div className="flex items-center gap-1.5 justify-end pt-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-xs"
                          onClick={() => setIsCreatingWs(false)}
                        >
                          Hủy
                        </Button>
                        <Button
                          type="submit"
                          size="sm"
                          className="h-6 px-2.5 text-xs bg-blue-600 hover:bg-blue-700 text-white"
                          disabled={isSubmittingWs || !newWsName.trim()}
                        >
                          {isSubmittingWs ? <Loader2 className="w-3 h-3 animate-spin" /> : "Tạo"}
                        </Button>
                      </div>
                    </form>
                  )}
                </div>
              </PopoverContent>
            </Popover>
          </div>
          
          {selectedGraph ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
              <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0 animate-pulse"></span>
              Đang kết nối: {selectedGraph.name}
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50 text-gray-500 text-xs font-semibold">
              <span className="w-2 h-2 rounded-full bg-gray-400 flex-shrink-0"></span>
              Chưa chọn Database
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
