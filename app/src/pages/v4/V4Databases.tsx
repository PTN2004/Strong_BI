import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDatabase } from "@/contexts/DatabaseContext";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { 
  Database, Trash2, Upload, Plus, Eye, Loader2, 
  Server, HardDrive, RefreshCw, Network, Edit3
} from "lucide-react";
import { buildApiUrl, API_CONFIG } from "@/config/api";
import { csrfHeaders } from "@/lib/csrf";
import SchemaViewer from "@/components/schema/SchemaViewer";

const DB_OPTIONS = [
  { id: 'postgres', label: 'PostgreSQL', icon: Database },
  { id: 'mysql', label: 'MySQL', icon: Database },
  { id: 'snowflake', label: 'Snowflake', icon: Server },
  { id: 'sqlite', label: 'SQLite', icon: HardDrive },
];

const V4Databases = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isViewer = user?.role?.toLowerCase() === "viewer";
  const { graphs, selectedGraph, selectGraph, uploadSchema, deleteGraph, refreshGraphs } = useDatabase();
  const { toast } = useToast();

  const [showSchemaViewer, setShowSchemaViewer] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [refreshingGraphId, setRefreshingGraphId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Connection settings states
  const [activeTab, setActiveTab] = useState("connect");
  const [connectionMode, setConnectionMode] = useState<'url' | 'manual'>('manual');
  const [selectedDatabase, setSelectedDatabase] = useState("postgres");
  const [connectionUrl, setConnectionUrl] = useState("");
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState("5432");
  const [database, setDatabase] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [schema, setSchema] = useState("public");
  const [sqlitePath, setSqlitePath] = useState("");
  
  // Snowflake fields
  const [account, setAccount] = useState("");
  const [snowflakeSchema, setSnowflakeSchema] = useState("PUBLIC");
  const [warehouse, setWarehouse] = useState("COMPUTE_WH");
  const [authMode, setAuthMode] = useState<'password' | 'keypair'>('password');
  const [privateKey, setPrivateKey] = useState("");
  const [privateKeyPassphrase, setPrivateKeyPassphrase] = useState("");

  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionSteps, setConnectionSteps] = useState<{message: string, status: 'pending'|'success'|'error'}[]>([]);

  const addStep = (message: string, status: 'pending' | 'success' | 'error' = 'pending') => {
    setConnectionSteps(prev => {
      if (status === 'pending' && prev.length > 0) {
        const lastStep = prev[prev.length - 1];
        if (lastStep.status === 'pending') {
          const updated = [...prev];
          updated[updated.length - 1] = { ...lastStep, status: 'success' };
          return [...updated, { message, status }];
        }
      }
      if (status !== 'pending' && prev.length > 0) {
        const lastStep = prev[prev.length - 1];
        if (lastStep.status === 'pending') {
          const updated = [...prev];
          updated[updated.length - 1] = { ...lastStep, status };
          return updated;
        }
      }
      return [...prev, { message, status }];
    });
  };

  const handleRefresh = async (graphId: string) => {
    setRefreshingGraphId(graphId);
    try {
      const response = await fetch(buildApiUrl(`/graphs/${graphId}/refresh`), {
        method: 'POST',
        headers: csrfHeaders(),
        credentials: 'include',
      });

      if (!response.ok) throw new Error('Error khi đồng bộ lại cấu trúc');
      if (!response.body) throw new Error('Streaming response has no body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const delimiter = API_CONFIG.STREAM_BOUNDARY;

      const processChunk = (text: string) => {
        if (!text || !text.trim()) return;
        try {
          const obj = JSON.parse(text);
          if (obj.type === 'final_result') {
            if (obj.success) {
              toast({ title: "Thành công", description: "Đã đồng bộ lại dữ liệu thành công!" });
              setTimeout(refreshGraphs, 1000);
            } else {
              toast({ title: "Thất bại", description: obj.message || "Error đồng bộ", variant: "destructive" });
            }
          } else if (obj.type === 'error') {
            toast({ title: "Error", description: obj.message || "Gặp sự cố khi đồng bộ", variant: "destructive" });
          }
        } catch (e) {}
      };

      const pump = async (): Promise<void> => {
        const { done, value } = await reader.read();
        if (done) {
          if (buffer.length > 0) processChunk(buffer);
          setRefreshingGraphId(null);
          return;
        }
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split(delimiter);
        buffer = parts.pop() || '';
        for (const part of parts) processChunk(part);
        return pump();
      };

      await pump();
    } catch (error: any) {
      toast({ title: "Error đồng bộ", description: error.message, variant: "destructive" });
      setRefreshingGraphId(null);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await uploadSchema(file, file.name.split('.')[0]);
      toast({ title: "Tải Schema thành công", description: `Đã biên dịch thành công cấu trúc dữ liệu cho "${file.name}"` });
    } catch (error: any) {
      toast({ title: "Tải lên thất bại", description: error.message, variant: "destructive" });
    }
  };

  const handleDelete = async (graphId: string, name: string) => {
    if (!confirm(`Are you sure muốn xóa cấu trúc dữ liệu "${name}" không?`)) return;
    setIsDeleting(graphId);
    try {
      await deleteGraph(graphId);
      toast({ title: "Đã xóa thành công", description: `Đã loại bỏ cấu trúc dữ liệu "${name}" khỏi hệ thống.` });
    } catch (error: any) {
      toast({ title: "Delete thất bại", description: error.message, variant: "destructive" });
    } finally {
      setIsDeleting(null);
    }
  };

  const handleConnect = async () => {
    if (connectionMode === 'url') {
      if (!connectionUrl || !selectedDatabase) {
        toast({ title: "Thiếu thông tin", description: "Vui lòng chọn loại database and nhập chuỗi URL kết nối", variant: "destructive" });
        return;
      }
    } else {
      if (selectedDatabase === 'snowflake') {
        if (!account || !database || !username) {
          toast({ title: "Thiếu thông tin", description: "Vui lòng điền đầy đủ thông tin Snowflake", variant: "destructive" });
          return;
        }
      } else if (selectedDatabase === 'sqlite') {
        if (!sqlitePath) {
          toast({ title: "Thiếu thông tin", description: "Vui lòng nhập đường dẫn tuyệt đối đến file SQLite", variant: "destructive" });
          return;
        }
      } else {
        if (!selectedDatabase || !host || !port || !database || !username) {
          toast({ title: "Thiếu thông tin", description: "Vui lòng nhập đầy đủ các trường thông số bắt buộc", variant: "destructive" });
          return;
        }
      }
    }
    
    setIsConnecting(true);
    setConnectionSteps([]);
    
    try {
      let dbUrl = connectionUrl;
      if (connectionMode === 'manual') {
        if (selectedDatabase === 'snowflake') {
          const builtUrl = new URL(`snowflake://${account}/${database}/${snowflakeSchema}`);
          builtUrl.username = username;
          if (authMode === 'keypair' && privateKey) {
            builtUrl.searchParams.set('private_key', btoa(privateKey));
            if (privateKeyPassphrase) builtUrl.searchParams.set('private_key_passphrase', privateKeyPassphrase);
          } else {
            builtUrl.password = password;
          }
          builtUrl.searchParams.set('warehouse', warehouse);
          dbUrl = builtUrl.toString();
        } else if (selectedDatabase === 'sqlite') {
          let safePath = sqlitePath;
          if (!safePath.startsWith('/')) safePath = '/' + safePath;
          dbUrl = `sqlite://${safePath}`;
        } else {
          const protocol = selectedDatabase === 'mysql' ? 'mysql' : 'postgresql';
          const builtUrl = new URL(`${protocol}://${host}:${port}/${database}`);
          builtUrl.username = username;
          builtUrl.password = password;
          if (selectedDatabase === 'postgresql' && schema.trim()) {
            if (/[^a-zA-Z0-9_]/.test(schema.trim())) throw new Error('Tên schema không hợp lệ');
            builtUrl.searchParams.set('options', `-csearch_path=${schema.trim()}`);
          }
          dbUrl = builtUrl.toString();
        }
      }

      const response = await fetch(buildApiUrl('/database'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
        body: JSON.stringify({ url: dbUrl }),
        credentials: 'include',
      });

      if (!response.ok) throw new Error(`Connection Error (${response.status})`);
      if (!response.body) throw new Error('Streaming response has no body');
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      const processChunk = (text: string) => {
        if (!text || !text.trim()) return;
        try {
          const obj = JSON.parse(text);
          if (obj.type === 'reasoning_step') {
            addStep(obj.message || 'Đang xử lý...', 'pending');
          } else if (obj.type === 'final_result') {
            addStep(obj.message || 'Hoàn tất', obj.success ? 'success' : 'error');
            setIsConnecting(false);
            if (obj.success) {
              toast({ title: "Kết nối thành công", description: "Dữ liệu cấu trúc cơ sở dữ liệu đã được nạp thành công!" });
              setTimeout(async () => {
                await refreshGraphs();
                setConnectionSteps([]);
              }, 1000);
            } else {
              toast({ title: "Connection failed", description: obj.message, variant: "destructive" });
            }
          } else if (obj.type === 'error') {
            addStep(obj.message || 'Error', 'error');
            setIsConnecting(false);
            toast({ title: "Connection Error", description: obj.message, variant: "destructive" });
          }
        } catch (e) {}
      };

      const pump = async (): Promise<void> => {
        const { done, value } = await reader.read();
        if (done) {
          if (buffer.length > 0) processChunk(buffer);
          setIsConnecting(false);
          return;
        }
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split(API_CONFIG.STREAM_BOUNDARY);
        buffer = parts.pop() || '';
        for (const part of parts) processChunk(part);
        return pump();
      };

      await pump();
    } catch (error: any) {
      setIsConnecting(false);
      toast({ title: "Connection failed", description: error.message, variant: "destructive" });
    }
  };

  return (
    <div className="flex h-full w-full bg-white dark:bg-[#09090b] relative font-sans">
      
      {/* LEFT COLUMN: Data Sources List */}
      <div className="w-[320px] lg:w-[380px] border-r border-gray-100 dark:border-gray-800 flex flex-col bg-[#f8f9fc] dark:bg-black/50 shrink-0">
        <div className="p-6 pb-2 shrink-0 border-b border-transparent">
          <h1 className="text-xl font-bold tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
            Data Sources
          </h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 mb-4">Manage your connected databases and schemas.</p>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {graphs.length === 0 ? (
            <div className="p-6 text-center">
              <p className="text-gray-400 text-sm">Chưa có Data Source nào.</p>
            </div>
          ) : (
            graphs.map((graph) => {
              const isActive = selectedGraph?.id === graph.id;
              
              return (
                <div 
                  key={graph.id} 
                  className={cn(
                    "flex flex-col p-4 rounded-[16px] transition-all cursor-pointer border group",
                    isActive 
                      ? "bg-[#eff6ff] dark:bg-[#1d4ed8]/10 border-[#1d4ed8]/30 shadow-sm" 
                      : "bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 hover:border-[#1d4ed8]/20 hover:shadow-sm"
                  )}
                  onClick={() => selectGraph(graph)}
                >
                  <div className="flex items-start gap-3">
                    <Database className={cn("w-5 h-5 flex-shrink-0 mt-0.5", isActive ? "text-[#1d4ed8]" : "text-gray-400")} />
                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold text-gray-900 dark:text-gray-100 truncate text-sm">{graph.name}</h3>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className={cn(
                          "w-1.5 h-1.5 rounded-full flex-shrink-0", 
                          graph.status === 'active' ? "bg-emerald-500" : "bg-gray-400"
                        )} />
                        <span className="text-[10px] font-semibold tracking-wider uppercase text-gray-500">
                          {graph.status === 'active' ? 'ACTIVE' : 'INACTIVE'}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Action Icons aligned to bottom right */}
                  <div className="flex justify-end gap-1 mt-3">
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={(e) => { e.stopPropagation(); handleRefresh(graph.id); }}
                      disabled={refreshingGraphId === graph.id}
                      className={cn("h-7 w-7 rounded-full", isActive ? "text-[#1d4ed8] hover:bg-[#1d4ed8]/10" : "text-gray-400 hover:text-gray-700")}
                      title="Sync Database"
                    >
                      <RefreshCw className={cn("w-3.5 h-3.5", refreshingGraphId === graph.id ? "animate-spin" : "")} />
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={(e) => { e.stopPropagation(); navigate(`/databases/${graph.id}/semantic`); }}
                      className={cn("h-7 w-7 rounded-full", isActive ? "text-[#1d4ed8] hover:bg-[#1d4ed8]/10" : "text-gray-400 hover:text-gray-700")}
                      title="Semantic Layer"
                    >
                      <Network className="w-3.5 h-3.5" />
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={(e) => { e.stopPropagation(); setShowSchemaViewer(graph.id); }}
                      className={cn("h-7 w-7 rounded-full", isActive ? "text-[#1d4ed8] hover:bg-[#1d4ed8]/10" : "text-gray-400 hover:text-gray-700")}
                      title="View Schema JSON"
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      onClick={(e) => { e.stopPropagation(); navigate(`/databases/${graph.id}/metadata`); }}
                      className={cn("h-7 w-7 rounded-full", isActive ? "text-[#1d4ed8] hover:bg-[#1d4ed8]/10" : "text-gray-400 hover:text-gray-700")}
                      title="Edit Schema Metadata"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </Button>
                    {!isViewer && (
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        onClick={(e) => { e.stopPropagation(); handleDelete(graph.id, graph.name); }}
                        disabled={isDeleting === graph.id}
                        className="h-7 w-7 rounded-full text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10"
                        title="Delete Data Source"
                      >
                        {isDeleting === graph.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                      </Button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* RIGHT COLUMN: Add New Data Source Form */}
      <div className="flex-1 overflow-y-auto p-8 lg:p-12 relative bg-white dark:bg-[#09090b]">
        <div className="max-w-3xl">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Add New Data Source</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-8">Connect a live database or upload a static schema file.</p>
          
          <Tabs defaultValue="connect" className="w-full space-y-6">
            <TabsList className="bg-transparent h-12 p-0 w-full justify-start border-b border-gray-200 dark:border-gray-800 rounded-none gap-6">
              <TabsTrigger 
                value="connect" 
                className="h-12 px-0 bg-transparent rounded-none data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#1d4ed8] data-[state=active]:text-[#1d4ed8] text-gray-500 font-semibold text-sm transition-none"
              >
                Connect Database
              </TabsTrigger>
              <TabsTrigger 
                value="upload" 
                className="h-12 px-0 bg-transparent rounded-none data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#1d4ed8] data-[state=active]:text-[#1d4ed8] text-gray-500 font-semibold text-sm transition-none"
              >
                Upload Schema
              </TabsTrigger>
            </TabsList>

            <TabsContent value="connect" className="space-y-8 animate-in fade-in duration-300 mt-6">
              
              {/* Select Engine */}
              <div>
                <Label className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-4 block">SELECT ENGINE</Label>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {DB_OPTIONS.map((db) => {
                    const isSelected = selectedDatabase === db.id;
                    const Icon = db.icon;
                    return (
                      <button
                        key={db.id}
                        onClick={() => setSelectedDatabase(db.id)}
                        className={cn(
                          "flex flex-col items-center justify-center p-6 rounded-2xl border transition-all gap-3 bg-white dark:bg-gray-900 shadow-sm",
                          isSelected
                            ? "border-[#1d4ed8] bg-[#eff6ff]/50 dark:bg-[#1d4ed8]/10 ring-1 ring-[#1d4ed8]"
                            : "border-gray-200 dark:border-gray-800 hover:border-blue-300 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                        )}
                      >
                        <div className={cn("p-3 rounded-xl", isSelected ? "bg-[#1d4ed8] text-white shadow-md" : "bg-gray-100 dark:bg-gray-800 text-gray-500")}>
                          <Icon className="w-6 h-6" />
                        </div>
                        <span className={cn("text-sm font-semibold", isSelected ? "text-[#1d4ed8] dark:text-blue-400" : "text-gray-600 dark:text-gray-400")}>
                          {db.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Form Tabs (Credentials / URI) */}
              <Tabs value={connectionMode} onValueChange={(val) => setConnectionMode(val as 'url' | 'manual')} className="w-full">
                <TabsList className="bg-transparent h-10 p-0 w-full justify-start gap-6 border-b border-gray-200 dark:border-gray-800 rounded-none mb-6">
                  <TabsTrigger 
                    value="manual" 
                    className="h-10 px-0 bg-transparent rounded-none data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#1d4ed8] data-[state=active]:text-[#1d4ed8] text-gray-500 font-semibold text-sm transition-none flex items-center gap-2"
                  >
                    Credentials
                  </TabsTrigger>
                  <TabsTrigger 
                    value="url" 
                    className="h-10 px-0 bg-transparent rounded-none data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#1d4ed8] data-[state=active]:text-[#1d4ed8] text-gray-500 font-semibold text-sm transition-none flex items-center gap-2"
                  >
                    Connection URI
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="manual" className="space-y-5 animate-in fade-in duration-300">
                  {selectedDatabase === 'snowflake' ? (
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs font-bold text-gray-600">Account (org-account)</Label>
                          <Input value={account} onChange={e => setAccount(e.target.value)} placeholder="e.g. xyz12345-us-east-1" className="h-12 bg-gray-50 dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8]" />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs font-bold text-gray-600">Database Name</Label>
                          <Input value={database} onChange={e => setDatabase(e.target.value)} placeholder="e.g. SNOWFLAKE_SAMPLE_DATA" className="h-12 bg-gray-50 dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8]" />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs font-bold text-gray-600">Schema</Label>
                          <Input value={snowflakeSchema} onChange={e => setSnowflakeSchema(e.target.value)} placeholder="PUBLIC" className="h-12 bg-gray-50 dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8]" />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs font-bold text-gray-600">Warehouse</Label>
                          <Input value={warehouse} onChange={e => setWarehouse(e.target.value)} placeholder="COMPUTE_WH" className="h-12 bg-gray-50 dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8]" />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs font-bold text-gray-600">Username</Label>
                        <Input value={username} onChange={e => setUsername(e.target.value)} className="h-12 bg-gray-50 dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8]" />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs font-bold text-gray-600">Password</Label>
                        <Input type="password" value={password} onChange={e => setPassword(e.target.value)} className="h-12 bg-gray-50 dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8]" />
                      </div>
                    </div>
                  ) : selectedDatabase === 'sqlite' ? (
                    <div className="space-y-2">
                      <Label className="text-xs font-bold text-gray-600">Absolute File Path</Label>
                      <Input value={sqlitePath} onChange={e => setSqlitePath(e.target.value)} placeholder="/Users/name/data/db.sqlite3" className="h-12 bg-gray-50 dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8]" />
                    </div>
                  ) : (
                    <div className="space-y-5">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs font-semibold text-gray-600">Host</Label>
                          <Input value={host} onChange={e => setHost(e.target.value)} placeholder="localhost" className="h-11 bg-[#f8f9fc] dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8] focus:ring-[#1d4ed8]/20" />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs font-semibold text-gray-600">Port</Label>
                          <Input value={port} onChange={e => setPort(e.target.value)} placeholder={selectedDatabase === 'mysql' ? "3306" : "5432"} className="h-11 bg-[#f8f9fc] dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8] focus:ring-[#1d4ed8]/20" />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs font-semibold text-gray-600">Database Name</Label>
                          <Input value={database} onChange={e => setDatabase(e.target.value)} placeholder="my_database" className="h-11 bg-[#f8f9fc] dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8] focus:ring-[#1d4ed8]/20" />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs font-semibold text-gray-600">Schema Name (PostgreSQL)</Label>
                          <Input value={schema} onChange={e => setSchema(e.target.value)} placeholder="public" disabled={selectedDatabase !== 'postgresql'} className="h-11 bg-[#f8f9fc] dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8] focus:ring-[#1d4ed8]/20 disabled:opacity-50" />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs font-semibold text-gray-600">Username</Label>
                          <Input value={username} onChange={e => setUsername(e.target.value)} className="h-11 bg-[#f8f9fc] dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8] focus:ring-[#1d4ed8]/20" />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs font-semibold text-gray-600">Password</Label>
                          <Input type="password" value={password} onChange={e => setPassword(e.target.value)} className="h-11 bg-[#f8f9fc] dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8] focus:ring-[#1d4ed8]/20" />
                        </div>
                      </div>
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="url" className="space-y-4 animate-in fade-in duration-300">
                  <div className="space-y-2">
                    <Label className="text-xs font-bold text-gray-600">Connection String (URI)</Label>
                    <Input 
                      value={connectionUrl} 
                      onChange={e => setConnectionUrl(e.target.value)} 
                      placeholder="postgresql://user:password@localhost:5432/mydb" 
                      className="h-12 font-mono text-sm bg-gray-50 dark:bg-gray-900 rounded-xl border-transparent focus:bg-white focus:border-[#1d4ed8]" 
                    />
                  </div>
                </TabsContent>
              </Tabs>

              {/* Action Buttons */}
              <div className="pt-2">
                <Button 
                  onClick={handleConnect} 
                  disabled={isConnecting} 
                  className="w-full h-12 rounded-xl bg-[#1d4ed8] hover:bg-[#1e40af] text-white font-semibold text-sm shadow-md transition-all"
                >
                  {isConnecting ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Plus className="w-5 h-5 mr-2" />}
                  Connect & Generate Schema
                </Button>
              </div>

              {/* Loading Steps UI */}
              {isConnecting && connectionSteps.length > 0 && (
                <div className="bg-gray-50 dark:bg-gray-900/50 border border-gray-100 dark:border-gray-800 rounded-2xl p-4 space-y-2 animate-in fade-in slide-in-from-bottom-2">
                  <p className="text-xs font-bold text-gray-500 mb-3 uppercase tracking-wider">Connection Process</p>
                  {connectionSteps.map((step, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      {step.status === 'pending' ? (
                        <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                      ) : step.status === 'success' ? (
                        <div className="w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center">
                          <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                        </div>
                      ) : (
                        <div className="w-4 h-4 rounded-full bg-red-500 flex items-center justify-center">
                          <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" /></svg>
                        </div>
                      )}
                      <span className={cn(
                        "font-medium",
                        step.status === 'error' ? "text-red-600" : 
                        step.status === 'success' ? "text-emerald-600" : "text-gray-700 dark:text-gray-300"
                      )}>
                        {step.message}
                      </span>
                    </div>
                  ))}
                </div>
              )}

            </TabsContent>

            <TabsContent value="upload" className="space-y-6 animate-in fade-in duration-300 mt-6">
              <div className="border-2 border-dashed border-gray-200 dark:border-gray-800 rounded-3xl p-12 text-center bg-gray-50 dark:bg-gray-900/20 flex flex-col items-center justify-center">
                <div className="w-16 h-16 rounded-full bg-blue-50 dark:bg-blue-500/10 flex items-center justify-center mb-4 text-[#1d4ed8]">
                  <Upload className="w-8 h-8" />
                </div>
                <h3 className="font-bold text-gray-900 dark:text-white mb-2 text-lg">Upload JSON Schema</h3>
                <p className="text-gray-500 text-sm max-w-md mx-auto mb-6">
                  Select a generated schema JSON file to upload to the workspace. The filename will be used as the database name.
                </p>
                <input type="file" ref={fileInputRef} onChange={handleFileSelect} className="hidden" accept=".json" />
                <Button 
                  onClick={() => fileInputRef.current?.click()} 
                  className="rounded-full px-8 h-12 shadow-sm bg-white text-gray-900 hover:bg-gray-100 border border-gray-200 font-semibold"
                >
                  Browse File
                </Button>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {showSchemaViewer && (
        <SchemaViewer 
          isOpen={!!showSchemaViewer} 
          onClose={() => setShowSchemaViewer(null)} 
          graphId={selectedGraph?.id || ''}
        />
      )}
    </div>
  );
};

export default V4Databases;
