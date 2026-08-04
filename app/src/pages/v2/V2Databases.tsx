import React, { useRef, useState } from "react";
import { useDatabase } from "@/contexts/DatabaseContext";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { 
  Database, Trash2, Upload, Plus, Eye, Check, Loader2, 
  CheckCircle2, XCircle, FileCode, RefreshCw, Server, 
  HardDrive, DatabaseZap, KeyRound, Link 
} from "lucide-react";
import { buildApiUrl, API_CONFIG } from "@/config/api";
import { csrfHeaders } from "@/lib/csrf";
import SchemaViewer from "@/components/schema/SchemaViewer";

interface ConnectionStep {
  message: string;
  status: 'pending' | 'success' | 'error';
}

const DB_OPTIONS = [
  { id: 'postgres', label: 'PostgreSQL', icon: Database },
  { id: 'mysql', label: 'MySQL', icon: Database },
  { id: 'snowflake', label: 'Snowflake', icon: Server },
  { id: 'sqlite', label: 'SQLite', icon: HardDrive },
];

const V2Databases = () => {
  const { user } = useAuth();
  const isViewer = user?.role?.toLowerCase() === "viewer";
  const { graphs, selectedGraph, selectGraph, uploadSchema, deleteGraph, refreshGraphs } = useDatabase();
  const { toast } = useToast();

  const [showSchemaViewer, setShowSchemaViewer] = useState(false);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [refreshingGraphId, setRefreshingGraphId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Connection settings states
  const [activeTab, setActiveTab] = useState("connect");
  const [connectionMode, setConnectionMode] = useState<'url' | 'manual'>('manual');
  const [selectedDatabase, setSelectedDatabase] = useState("postgres");
  const [connectionUrl, setConnectionUrl] = useState("");
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState("");
  const [database, setDatabase] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [schema, setSchema] = useState("");
  const [sqlitePath, setSqlitePath] = useState("");
  
  // Snowflake fields
  const [account, setAccount] = useState("");
  const [snowflakeSchema, setSnowflakeSchema] = useState("PUBLIC");
  const [warehouse, setWarehouse] = useState("COMPUTE_WH");
  const [authMode, setAuthMode] = useState<'password' | 'keypair'>('password');
  const [privateKey, setPrivateKey] = useState("");
  const [privateKeyPassphrase, setPrivateKeyPassphrase] = useState("");

  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionSteps, setConnectionSteps] = useState<ConnectionStep[]>([]);

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
    <div className="flex w-full h-[calc(100vh-56px)] overflow-hidden bg-background">
      
      {/* Left Sidebar - Database List */}
      <div className="w-80 border-r border-border bg-card/30 flex flex-col shrink-0">
        <div className="p-5 border-b border-border/50 bg-background/50 backdrop-blur-sm">
          <h2 className="font-bold text-base text-foreground flex items-center gap-2">
            <Database className="w-5 h-5 text-primary" />
            Data Sources
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Manage your connected databases and schemas.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {graphs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-center border-2 border-dashed border-border rounded-xl">
              <Database className="w-8 h-8 text-muted-foreground mb-2 opacity-50" />
              <p className="text-sm font-medium text-muted-foreground">No databases found</p>
            </div>
          ) : (
            graphs.map((graph) => {
              const isSelected = selectedGraph?.id === graph.id;
              return (
                <div
                  key={graph.id}
                  className={cn(
                    "group flex flex-col p-4 rounded-2xl border transition-all cursor-pointer relative overflow-hidden",
                    isSelected 
                      ? "bg-primary/5 border-primary shadow-sm" 
                      : "bg-card border-border/60 hover:border-primary/40 hover:bg-muted/30 hover:shadow-sm"
                  )}
                  onClick={() => selectGraph(graph.id)}
                >
                  {isSelected && (
                    <div className="absolute top-0 right-0 w-16 h-16 bg-primary/10 rounded-bl-[100px] -z-10" />
                  )}
                  
                  <div className="flex items-start justify-between mb-3 z-10">
                    <div className="flex items-center gap-3">
                      <div className={cn("p-2 rounded-xl flex items-center justify-center", isSelected ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground")}>
                        <Database className="w-5 h-5" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm font-bold text-foreground truncate max-w-[120px]">{graph.name}</span>
                        <div className="flex items-center gap-1 mt-0.5">
                          <div className={cn("w-1.5 h-1.5 rounded-full", isSelected ? "bg-success" : "bg-muted-foreground")} />
                          <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">
                            {isSelected ? "Active" : "Inactive"}
                          </span>
                        </div>
                      </div>
                    </div>
                    {graph.isDemo && (
                      <Badge variant="secondary" className="text-[9px] px-1.5 py-0">DEMO</Badge>
                    )}
                  </div>

                  <div className="flex items-center justify-end gap-1.5 pt-3 border-t border-border/50 z-10">
                    {!graph.isDemo && !isViewer && (
                      <Button
                        variant="ghost" size="icon" className="h-7 w-7 rounded-lg text-muted-foreground hover:bg-primary/10 hover:text-primary"
                        disabled={refreshingGraphId === graph.id}
                        onClick={(e) => { e.stopPropagation(); handleRefresh(graph.id); }}
                      >
                        {refreshingGraphId === graph.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                      </Button>
                    )}
                    <Button
                      variant="ghost" size="icon" className="h-7 w-7 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
                      onClick={(e) => { e.stopPropagation(); setShowSchemaViewer(true); }}
                    >
                      <Eye className="w-3.5 h-3.5" />
                    </Button>
                    {!graph.isDemo && !isViewer && (
                      <Button
                        variant="ghost" size="icon" className="h-7 w-7 rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                        disabled={isDeleting === graph.id}
                        onClick={(e) => { e.stopPropagation(); handleDelete(graph.id, graph.name); }}
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

      {/* Main Workspace - Connection & Upload */}
      <div className="flex-1 overflow-y-auto p-8 lg:p-12">
        <div className="max-w-4xl mx-auto">
          {isViewer ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-20 h-20 rounded-3xl bg-primary/10 flex items-center justify-center mb-6 text-primary">
                <DatabaseZap className="w-10 h-10" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight mb-2">Viewer Mode Active</h1>
              <p className="text-sm text-muted-foreground max-w-md leading-relaxed">
                You are currently in viewer mode. Only administrators or analysts can configure new database connections or upload schemas.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Add New Data Source</h1>
                <p className="text-sm text-muted-foreground mt-1">Connect a live database or upload a static schema file.</p>
              </div>

              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="w-full max-w-md grid grid-cols-2 h-12 bg-muted/50 rounded-xl p-1 mb-6">
                  <TabsTrigger value="connect" className="rounded-lg text-xs font-bold data-[state=active]:bg-background data-[state=active]:shadow-sm">
                    Connect Database
                  </TabsTrigger>
                  <TabsTrigger value="upload" className="rounded-lg text-xs font-bold data-[state=active]:bg-background data-[state=active]:shadow-sm">
                    Upload Schema
                  </TabsTrigger>
                </TabsList>

                {/* CONNECT DATABASE TAB */}
                <TabsContent value="connect" className="space-y-6 m-0 animate-in fade-in duration-300">
                  <div className="bg-card border border-border rounded-2xl shadow-sm p-6 sm:p-8">
                    
                    {/* Visual Database Grid */}
                    <div className="space-y-3 mb-8">
                      <Label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Select Engine</Label>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {DB_OPTIONS.map((db) => {
                          const isSelected = selectedDatabase === db.id;
                          return (
                            <div 
                              key={db.id} 
                              onClick={() => { setSelectedDatabase(db.id); setConnectionMode(db.id === 'sqlite' ? 'manual' : 'manual'); }}
                              className={cn(
                                "group cursor-pointer rounded-2xl border-2 p-5 flex flex-col items-center justify-center gap-3 transition-all",
                                isSelected ? "border-primary bg-primary/5 shadow-md" : "border-border/50 bg-background hover:border-primary/40 hover:bg-muted/30"
                              )}
                            >
                              <div className={cn("p-3 rounded-xl transition-colors", isSelected ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground group-hover:text-foreground group-hover:bg-muted/80")}>
                                <db.icon className="w-6 h-6" />
                              </div>
                              <span className="text-sm font-bold text-foreground">{db.label}</span>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {isConnecting ? (
                      <div className="bg-[#0f172a] rounded-2xl border border-slate-800 p-6 shadow-inner font-mono text-xs overflow-hidden h-[300px] flex flex-col relative">
                        <div className="absolute top-0 left-0 right-0 h-8 bg-slate-900 border-b border-slate-800 flex items-center px-4 gap-2">
                          <div className="w-3 h-3 rounded-full bg-rose-500" />
                          <div className="w-3 h-3 rounded-full bg-amber-500" />
                          <div className="w-3 h-3 rounded-full bg-emerald-500" />
                          <span className="ml-2 text-slate-500 text-[10px]">terminal - connection process</span>
                        </div>
                        <div className="flex-1 overflow-y-auto pt-6 space-y-2 text-slate-300 scrollbar-visible">
                          {connectionSteps.map((step, i) => (
                            <div key={i} className="flex items-start gap-2">
                              <span className="text-slate-500 shrink-0">[{new Date().toLocaleTimeString()}]</span>
                              {step.status === 'success' && <span className="text-emerald-400 font-bold shrink-0">✓</span>}
                              {step.status === 'error' && <span className="text-rose-400 font-bold shrink-0">✗</span>}
                              {step.status === 'pending' && <Loader2 className="w-3.5 h-3.5 animate-spin text-sky-400 shrink-0 mt-0.5" />}
                              <span className={cn("flex-1 leading-relaxed", step.status === 'error' ? 'text-rose-400' : 'text-slate-300')}>
                                {step.message}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-6 animate-in fade-in duration-300">
                        {selectedDatabase !== 'sqlite' && (
                          <div className="flex border-b border-border mb-6">
                            <button
                              onClick={() => setConnectionMode('manual')}
                              className={cn("px-6 py-3 text-sm font-bold border-b-2 -mb-[1px] transition-colors", connectionMode === 'manual' ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}
                            >
                              <div className="flex items-center gap-2"><KeyRound className="w-4 h-4" /> Credentials</div>
                            </button>
                            <button
                              onClick={() => setConnectionMode('url')}
                              className={cn("px-6 py-3 text-sm font-bold border-b-2 -mb-[1px] transition-colors", connectionMode === 'url' ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}
                            >
                              <div className="flex items-center gap-2"><Link className="w-4 h-4" /> Connection URI</div>
                            </button>
                          </div>
                        )}

                        {connectionMode === 'url' && selectedDatabase !== 'sqlite' ? (
                          <div className="space-y-3">
                            <Label className="text-sm font-bold text-foreground">Connection String (URI)</Label>
                            <Input 
                              placeholder={
                                selectedDatabase === "postgres" ? "postgresql://user:pass@host:port/db" :
                                selectedDatabase === "mysql" ? "mysql+pymysql://user:pass@host:port/db" :
                                "snowflake://user:pass@account/db?warehouse=wh"
                              }
                              value={connectionUrl} 
                              onChange={(e) => setConnectionUrl(e.target.value)} 
                              className="h-12 rounded-xl bg-background border-border font-mono text-sm" 
                            />
                            <p className="text-xs text-muted-foreground">Standard SQLAlchemy connection string format.</p>
                          </div>
                        ) : (
                          <>
                            {selectedDatabase === "snowflake" ? (
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                <div className="space-y-2">
                                  <Label className="text-xs font-bold text-muted-foreground">Account Identifier</Label>
                                  <Input value={account} onChange={(e) => setAccount(e.target.value)} className="h-10 rounded-xl" />
                                </div>
                                <div className="space-y-2">
                                  <Label className="text-xs font-bold text-muted-foreground">Warehouse</Label>
                                  <Input value={warehouse} onChange={(e) => setWarehouse(e.target.value)} className="h-10 rounded-xl" />
                                </div>
                                <div className="space-y-2">
                                  <Label className="text-xs font-bold text-muted-foreground">Database</Label>
                                  <Input value={database} onChange={(e) => setDatabase(e.target.value)} className="h-10 rounded-xl" />
                                </div>
                                <div className="space-y-2">
                                  <Label className="text-xs font-bold text-muted-foreground">Username</Label>
                                  <Input value={username} onChange={(e) => setUsername(e.target.value)} className="h-10 rounded-xl" />
                                </div>
                                <div className="space-y-2 md:col-span-2">
                                  <Label className="text-xs font-bold text-muted-foreground">Password</Label>
                                  <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="h-10 rounded-xl" />
                                </div>
                              </div>
                            ) : selectedDatabase === "sqlite" ? (
                              <div className="space-y-3">
                                <Label className="text-sm font-bold text-foreground">Absolute File Path</Label>
                                <Input 
                                  placeholder="/var/lib/data/mydb.sqlite" 
                                  value={sqlitePath} 
                                  onChange={(e) => setSqlitePath(e.target.value)} 
                                  className="h-12 rounded-xl bg-background border-border font-mono text-sm" 
                                />
                                <p className="text-xs text-muted-foreground">Enter the absolute path to your SQLite database file on the server filesystem.</p>
                              </div>
                            ) : (
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                <div className="space-y-2 md:col-span-2">
                                  <Label className="text-xs font-bold text-muted-foreground">Host</Label>
                                  <Input value={host} onChange={(e) => setHost(e.target.value)} className="h-10 rounded-xl" placeholder="db.company.com or 127.0.0.1" />
                                </div>
                                <div className="space-y-2">
                                  <Label className="text-xs font-bold text-muted-foreground">Port</Label>
                                  <Input placeholder={selectedDatabase === "mysql" ? "3306" : "5432"} value={port} onChange={(e) => setPort(e.target.value)} className="h-10 rounded-xl font-mono" />
                                </div>
                                <div className="space-y-2">
                                  <Label className="text-xs font-bold text-muted-foreground">Database Name</Label>
                                  <Input value={database} onChange={(e) => setDatabase(e.target.value)} className="h-10 rounded-xl" />
                                </div>
                                {selectedDatabase === "postgres" && (
                                  <div className="space-y-2 md:col-span-2">
                                    <Label className="text-xs font-bold text-muted-foreground">Schema Name</Label>
                                    <Input placeholder="public" value={schema} onChange={(e) => setSchema(e.target.value)} className="h-10 rounded-xl" />
                                  </div>
                                )}
                                <div className="space-y-2">
                                  <Label className="text-xs font-bold text-muted-foreground">Username</Label>
                                  <Input value={username} onChange={(e) => setUsername(e.target.value)} className="h-10 rounded-xl" />
                                </div>
                                <div className="space-y-2">
                                  <Label className="text-xs font-bold text-muted-foreground">Password</Label>
                                  <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="h-10 rounded-xl" />
                                </div>
                              </div>
                            )}
                          </>
                        )}
                        
                        <div className="pt-6 border-t border-border/50">
                          <Button
                            onClick={handleConnect}
                            className="w-full h-12 rounded-xl font-bold text-sm shadow-md"
                          >
                            <Plus className="w-5 h-5 mr-2" /> Connect & Generate Schema
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </TabsContent>

                {/* UPLOAD SCHEMA TAB */}
                <TabsContent value="upload" className="space-y-6 m-0 animate-in fade-in duration-300">
                  <div className="bg-card border border-border rounded-2xl shadow-sm p-6 sm:p-12 text-center flex flex-col items-center justify-center min-h-[400px]">
                    <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mb-6">
                      <FileCode className="w-10 h-10 text-primary" />
                    </div>
                    <h3 className="text-xl font-bold mb-2">Upload Schema File</h3>
                    <p className="text-sm text-muted-foreground max-w-sm mb-8 leading-relaxed">
                      Supports SQL DDL, CSV, or JSON schema files for quick ingestion into the graph knowledge base without an active connection.
                    </p>
                    
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".sql,.csv,.json"
                      onChange={handleFileSelect}
                      style={{ display: "none" }}
                    />
                    <Button 
                      onClick={() => fileInputRef.current?.click()}
                      className="h-12 px-8 rounded-xl font-bold text-sm shadow-md"
                    >
                      <Upload className="w-5 h-5 mr-2" /> Browse Files
                    </Button>
                    <p className="text-xs text-muted-foreground mt-4 font-mono">.sql • .csv • .json</p>
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          )}
        </div>
      </div>

      <SchemaViewer
        isOpen={showSchemaViewer}
        onClose={() => setShowSchemaViewer(false)}
        side="right"
        sidebarWidth={0}
      />
    </div>
  );
};

export default V2Databases;
