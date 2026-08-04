import React, { useState, useEffect, useRef } from "react";
import { useSettings, AIVendor } from "@/contexts/SettingsContext";
import { useAuth } from "@/contexts/AuthContext";
import { useDatabase } from "@/contexts/DatabaseContext";
import { DatabaseService } from "@/services/database";
import { AuthService } from "@/services/auth";
import { TokenService, Token } from "@/services/tokens";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { 
  Settings, Users, Key, ShieldAlert, Code, Trash2, Copy, Check, 
  Loader2, Cpu, Sliders, CheckCircle2, XCircle, Sparkles, HelpCircle,
  UserPlus, Shield, Eye, BarChart3, RefreshCw, UserX, AlertTriangle
} from "lucide-react";
import { useApiKeyValidation } from "@/hooks/useApiKeyValidation";
import { AI_VENDORS, getVendorConfig, DEFAULT_MODEL } from "@/utils/vendorConfig";
import { buildApiUrl } from "@/config/api";

type Tab = "ai" | "team" | "dev" | "system";

const V2Settings = () => {
  const [activeTab, setActiveTab] = useState<Tab>("ai");

  const { 
    vendor, apiKey, modelName, isApiKeyValid, customEndpoint,
    setVendor, setApiKey, setModelName, setIsApiKeyValid, setCustomEndpoint, clearSettings 
  } = useSettings();
  const { user } = useAuth();
  const { selectedGraph } = useDatabase();
  const { toast } = useToast();

  const [tempVendor, setTempVendor] = useState<AIVendor>(vendor);
  const [tempApiKey, setTempApiKey] = useState(apiKey || "");
  const [tempModelName, setTempModelName] = useState(modelName);
  const [tempApiBase, setTempApiBase] = useState(customEndpoint || "");
  
  const { message: validationMessage, status: validationStatus, isValidating, validateApiKey, clearValidation } = useApiKeyValidation();

  const [useMemory, setUseMemory] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('queryweaver_use_memory');
      return saved === null ? true : saved === 'true';
    }
    return true;
  });

  const [useRulesFromDatabase, setUseRulesFromDatabase] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('queryweaver_use_rules_from_database');
      return saved === null ? false : saved === 'true';
    }
    return false;
  });

  const [rules, setRules] = useState('');
  const [isLoadingRules, setIsLoadingRules] = useState(false);
  const [initialRulesLoaded, setInitialRulesLoaded] = useState(false);

  const loadedRulesRef = useRef<string>('');
  const currentRulesRef = useRef<string>('');
  const currentGraphIdRef = useRef<string | null>(null);
  const useRulesFromDatabaseRef = useRef<boolean>(true);
  const initialRulesLoadedRef = useRef<boolean>(false);

  // Admin states
  const [usersList, setUsersList] = useState<any[]>([]);
  const [isAdminLoading, setIsAdminLoading] = useState(false);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);
  const [confirmDeleteUser, setConfirmDeleteUser] = useState<any | null>(null);
  const [systemInfo, setSystemInfo] = useState<any>(null);

  // Create user modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({ firstName: '', lastName: '', email: '', password: '', role: 'analyst' });
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  // Token states
  const [tokens, setTokens] = useState<Token[]>([]);
  const [isTokensLoading, setIsTokensLoading] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);

  const fetchTokens = async () => {
    setIsTokensLoading(true);
    try {
      const data = await TokenService.listTokens();
      setTokens(data.tokens || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsTokensLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "dev") {
      fetchTokens();
    }
  }, [activeTab]);

  const handleGenerateToken = async () => {
    try {
      const data = await TokenService.generateToken();
      setNewToken((data as any).token || data.token_id || "generated-token");
      fetchTokens();
      toast({ title: "Token Generated", description: "Save this token now. You won't be able to see it again." });
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
  };

  const handleDeleteToken = async (tokenId: string) => {
    try {
      await TokenService.deleteToken(tokenId);
      fetchTokens();
      toast({ title: "Token Deleted" });
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
  };

  const isAdmin = user?.role?.toLowerCase() === "admin";
  const isViewer = user?.role?.toLowerCase() === "viewer";

  // Load Rules
  useEffect(() => {
    const loadRules = async () => {
      if (!selectedGraph) {
        setRules('');
        setIsLoadingRules(false);
        setInitialRulesLoaded(false);
        loadedRulesRef.current = '';
        currentGraphIdRef.current = null;
        return;
      }
      
      currentGraphIdRef.current = selectedGraph.id;
      
      if (!useRulesFromDatabase) {
        setIsLoadingRules(false);
        setInitialRulesLoaded(true);
        return;
      }
      
      try {
        setIsLoadingRules(true);
        setInitialRulesLoaded(false);
        const userRules = await DatabaseService.getUserRules(selectedGraph.id);
        const rulesValue = userRules || '';
        setRules(rulesValue);
        loadedRulesRef.current = rulesValue;
      } catch (error) {
        console.error('Failed to load user rules:', error);
        toast({
          title: "Error tải cấu hình",
          description: "Could not load user rules from database",
          variant: "destructive",
        });
      } finally {
        setIsLoadingRules(false);
        setInitialRulesLoaded(true);
        initialRulesLoadedRef.current = true;
      }
    };
    
    loadRules();
  }, [selectedGraph?.id, useRulesFromDatabase]);

  useEffect(() => {
    useRulesFromDatabaseRef.current = useRulesFromDatabase;
  }, [useRulesFromDatabase]);

  useEffect(() => {
    currentRulesRef.current = rules;
  }, [rules]);

  // Save rules on unmount
  useEffect(() => {
    return () => {
      const graphId = currentGraphIdRef.current;
      const loadedRules = loadedRulesRef.current;
      const currentRules = currentRulesRef.current;
      const shouldUseDb = useRulesFromDatabaseRef.current;
      const isLoaded = initialRulesLoadedRef.current;
      
      if (graphId && shouldUseDb && currentRules !== loadedRules && isLoaded) {
        DatabaseService.updateUserRules(graphId, currentRules)
          .catch(err => console.error('Failed to save rules on unmount:', err));
      }
    };
  }, []);

  useEffect(() => {
    localStorage.setItem('queryweaver_use_memory', String(useMemory));
  }, [useMemory]);

  useEffect(() => {
    localStorage.setItem('queryweaver_use_rules_from_database', String(useRulesFromDatabase));
  }, [useRulesFromDatabase]);

  const prevVendorRef = useRef<AIVendor>(tempVendor);
  useEffect(() => {
    if (tempVendor === prevVendorRef.current) return;
    prevVendorRef.current = tempVendor;
    const vendorConfig = AI_VENDORS.find(v => v.value === tempVendor);
    if (vendorConfig) {
      setTempModelName(vendorConfig.exampleModel);
    }
  }, [tempVendor]);

  useEffect(() => {
    setTempVendor(vendor);
    setTempApiKey(apiKey || "");
    setTempModelName(modelName);
    setTempApiBase(customEndpoint || "");
    
    fetchSystemInfo();

    if (isAdmin) {
      fetchUsers();
    }
  }, [vendor, apiKey, modelName, isAdmin]);

  const fetchSystemInfo = async () => {
    try {
      const response = await fetch(buildApiUrl('/settings/system-info'), {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setSystemInfo(data);
      }
    } catch (e) {
      console.error('Failed to fetch system info:', e);
    }
  };

  const fetchUsers = async () => {
    setIsAdminLoading(true);
    try {
      const data = await AuthService.getUsers();
      setUsersList(data);
    } catch (error: any) {
      console.error(error);
    } finally {
      setIsAdminLoading(false);
    }
  };

  const handleSaveApiKey = async () => {
    const isValid = await validateApiKey(tempApiKey, tempVendor, tempModelName, tempApiBase);
    
    if (isValid) {
      setVendor(tempVendor);
      setApiKey(tempApiKey);
      setModelName(tempModelName);
      setCustomEndpoint(tempApiBase);
      setIsApiKeyValid(true);
      toast({
        title: "AI Settings Saved",
        description: "AI configuration and API key updated successfully.",
      });
    }
  };

  const handleClearApiKey = () => {
    setTempVendor('openai');
    setTempApiKey('');
    setTempModelName(DEFAULT_MODEL);
    setTempApiBase('');
    clearValidation();
    clearSettings();
    toast({
      title: "Settings cleared",
      description: "Cleared AI configuration from session memory.",
    });
  };

  const handleUpdateUser = async (userId: string, role: string, isActive: boolean) => {
    setUpdatingUserId(userId);
    try {
      await AuthService.updateUser(userId, role, isActive);
      toast({ title: "Updated", description: "Member info has been updated." });
      fetchUsers();
    } catch (error: any) {
      toast({ title: "Update failed", description: error.message || "Could not update member info.", variant: "destructive" });
    } finally {
      setUpdatingUserId(null);
    }
  };

  const handleDeleteUser = async (u: any) => {
    setConfirmDeleteUser(u);
  };

  const confirmDelete = async () => {
    if (!confirmDeleteUser) return;
    setDeletingUserId(confirmDeleteUser.id);
    try {
      await AuthService.deleteUser(confirmDeleteUser.id);
      toast({ title: "User deleted", description: `${confirmDeleteUser.firstName} ${confirmDeleteUser.lastName} has been removed.` });
      fetchUsers();
    } catch (error: any) {
      toast({ title: "Delete failed", description: error.message, variant: "destructive" });
    } finally {
      setDeletingUserId(null);
      setConfirmDeleteUser(null);
    }
  };

  const handleCreateUser = async () => {
    setCreateError('');
    if (!createForm.firstName.trim() || !createForm.email.trim() || !createForm.password.trim()) {
      setCreateError('First name, email and password are required.');
      return;
    }
    setIsCreating(true);
    try {
      await AuthService.createUser(createForm);
      toast({ title: "User created", description: `${createForm.firstName} has been added to the team.` });
      setShowCreateModal(false);
      setCreateForm({ firstName: '', lastName: '', email: '', password: '', role: 'analyst' });
      fetchUsers();
    } catch (error: any) {
      setCreateError(error.message || 'Failed to create user.');
    } finally {
      setIsCreating(false);
    }
  };

  const hasRulesChanges = rules !== loadedRulesRef.current;

  return (
    <div className="flex w-full h-[calc(100vh-56px)] overflow-hidden bg-background">
      
      {/* Sidebar Navigation */}
      <div className="w-64 border-r border-border bg-card/30 shrink-0 flex flex-col pt-6 px-4">
        <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-4 px-2">Settings</h2>
        <div className="space-y-1">
          <Button
            variant={activeTab === 'ai' ? "default" : "ghost"}
            className={cn("w-full justify-start text-xs font-semibold h-10", activeTab === 'ai' ? "" : "text-muted-foreground")}
            onClick={() => setActiveTab('ai')}
          >
            <Cpu className="w-4 h-4 mr-2" />
            AI Configuration
          </Button>
          <Button
            variant={activeTab === 'team' ? "default" : "ghost"}
            className={cn("w-full justify-start text-xs font-semibold h-10", activeTab === 'team' ? "" : "text-muted-foreground")}
            onClick={() => setActiveTab('team')}
          >
            <Users className="w-4 h-4 mr-2" />
            Team Management
          </Button>
          <Button
            variant={activeTab === 'dev' ? "default" : "ghost"}
            className={cn("w-full justify-start text-xs font-semibold h-10", activeTab === 'dev' ? "" : "text-muted-foreground")}
            onClick={() => setActiveTab('dev')}
          >
            <Code className="w-4 h-4 mr-2" />
            Developer / Tokens
          </Button>
          <Button
            variant={activeTab === 'system' ? "default" : "ghost"}
            className={cn("w-full justify-start text-xs font-semibold h-10", activeTab === 'system' ? "" : "text-muted-foreground")}
            onClick={() => setActiveTab('system')}
          >
            <Sliders className="w-4 h-4 mr-2" />
            System Info
          </Button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-8 lg:p-12">
        <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300">
          
          {/* TAB: AI CONFIGURATION */}
          {activeTab === 'ai' && (
            <div className="space-y-8">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">AI Configuration</h1>
                <p className="text-sm text-muted-foreground mt-1">Configure your LLM provider and query generation rules.</p>
              </div>

              <div className="bg-card border border-border rounded-2xl p-6 shadow-sm space-y-6">
                <div className="flex items-center gap-2 border-b border-border/50 pb-4">
                  <Key className="w-5 h-5 text-primary" />
                  <h3 className="text-base font-bold">API Credentials</h3>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-3">
                    <Label className="text-xs font-bold text-muted-foreground">Provider (Vendor)</Label>
                    <Select value={tempVendor} onValueChange={(val) => setTempVendor(val as AIVendor)}>
                      <SelectTrigger className="h-10 rounded-xl bg-background border-border text-sm">
                        <SelectValue placeholder="Select Vendor" />
                      </SelectTrigger>
                      <SelectContent className="rounded-xl border-border">
                        {AI_VENDORS.map((v) => (
                          <SelectItem key={v.value} value={v.value} className="text-sm">
                            {v.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-3">
                    <Label className="text-xs font-bold text-muted-foreground">Model Name</Label>
                    <Input 
                      value={tempModelName} 
                      onChange={(e) => setTempModelName(e.target.value)}
                      placeholder={getVendorConfig(tempVendor)?.exampleModel || "gpt-4o-mini"}
                      disabled={!tempApiKey.trim() && tempVendor !== 'vllm' && tempVendor !== 'ollama' && !tempApiBase.trim()}
                      className="h-10 rounded-xl bg-background border-border text-sm"
                    />
                  </div>
                </div>

                {['vllm', 'ollama', 'openai', 'azure', 'anthropic', 'cohere'].includes(tempVendor) && (
                  <div className="space-y-3">
                    <Label className="text-xs font-bold text-muted-foreground">API Base URL (Optional)</Label>
                    <Input 
                      value={tempApiBase} 
                      onChange={(e) => setTempApiBase(e.target.value)}
                      placeholder="e.g., http://localhost:11434 or https://your-proxy.com/v1"
                      className="h-10 rounded-xl bg-background border-border text-sm"
                    />
                  </div>
                )}

                {(tempVendor === 'vllm' || tempVendor === 'ollama') ? (
                  <Alert className="bg-primary/5 text-primary border-none rounded-xl">
                    <AlertDescription className="text-xs font-medium space-y-2">
                      <p>💡 <b>Host Server Config Tip:</b> Self-hosted models via vLLM / Ollama run directly on the enterprise backend server.</p>
                      <p className="text-[11px] opacity-85">You can configure API Base URL here or set <code>VLLM_API_BASE</code> / <code>OLLAMA_API_BASE</code> in the Backend <code>.env</code> file.</p>
                    </AlertDescription>
                  </Alert>
                ) : (
                  <div className="space-y-3">
                    <Label className="text-xs font-bold text-muted-foreground">API Key</Label>
                    <Input 
                      type="password"
                      value={tempApiKey} 
                      onChange={(e) => {
                        setTempApiKey(e.target.value);
                        clearValidation();
                      }}
                      placeholder={getVendorConfig(tempVendor)?.keyPrefix ? `${getVendorConfig(tempVendor)?.keyPrefix}...` : "Enter API Key..."}
                      className="h-10 rounded-xl bg-background border-border text-sm"
                    />
                  </div>
                )}

                {validationMessage && (
                  <Alert className={`border-none rounded-xl ${validationStatus === 'error' ? 'bg-destructive/10 text-destructive' : 'bg-success/10 text-success'}`}>
                    <AlertDescription className="text-xs font-bold flex items-center gap-1.5">
                      {validationStatus === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                      {validationMessage}
                    </AlertDescription>
                  </Alert>
                )}

                {isApiKeyValid && apiKey && (
                  <Alert className="bg-success/10 text-success border-none rounded-xl">
                    <AlertDescription className="text-xs font-bold flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      Active: {getVendorConfig(vendor)?.label} • {modelName}
                    </AlertDescription>
                  </Alert>
                )}

                <div className="flex justify-end gap-3 pt-4 border-t border-border/50">
                  <Button 
                    variant="outline"
                    onClick={handleClearApiKey}
                    disabled={!apiKey && !tempApiKey}
                    className="h-10 text-xs rounded-xl font-bold"
                  >
                    Clear Memory
                  </Button>
                  <Button 
                    onClick={handleSaveApiKey}
                    disabled={isValidating || (!tempApiKey.trim() && tempVendor !== 'vllm' && tempVendor !== 'ollama') || !tempModelName.trim()}
                    className="h-10 text-xs rounded-xl font-bold px-6"
                  >
                    {isValidating && <Loader2 className="mr-2 w-4 h-4 animate-spin" />}
                    Save Configuration
                  </Button>
                </div>
              </div>

              <div className="bg-card border border-border rounded-2xl p-6 shadow-sm space-y-6">
                <div className="flex items-center gap-2 border-b border-border/50 pb-4">
                  <Settings className="w-5 h-5 text-primary" />
                  <h3 className="text-base font-bold">Preferences & Rules</h3>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-background border border-border rounded-xl p-4 flex justify-between items-center shadow-sm">
                    <div className="space-y-1">
                      <Label className="text-sm font-bold text-foreground">Use AI Memory</Label>
                      <p className="text-xs text-muted-foreground">AI remembers previous conversations in this session.</p>
                    </div>
                    <Switch checked={useMemory} onCheckedChange={setUseMemory} />
                  </div>

                  <div className="bg-background border border-border rounded-xl p-4 flex justify-between items-center shadow-sm">
                    <div className="space-y-1">
                      <Label className="text-sm font-bold text-foreground">Database Rules</Label>
                      <p className="text-xs text-muted-foreground">Apply custom SQL generation rules.</p>
                    </div>
                    <Switch checked={useRulesFromDatabase} onCheckedChange={setUseRulesFromDatabase} />
                  </div>
                </div>

                {useRulesFromDatabase && (
                  <div className="bg-background border border-border rounded-xl p-5 space-y-4 shadow-sm">
                    <div className="flex justify-between items-center">
                      <Label className="text-sm font-bold text-foreground">Custom Query Generation Rules</Label>
                      <span className="text-xs font-medium text-muted-foreground">{rules.length}/5000 chars</span>
                    </div>
                    
                    {!selectedGraph ? (
                      <div className="text-center py-8 text-sm text-muted-foreground border-2 border-dashed border-border rounded-xl">
                        Please select a database in the Workspace to load specific rules.
                      </div>
                    ) : isLoadingRules ? (
                      <div className="flex items-center justify-center py-10">
                        <Loader2 className="w-6 h-6 animate-spin text-primary" />
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <Textarea
                          placeholder={`Example rules:\n- Always format dates in ISO standard (YYYY-MM-DD)\n- Limit rows to 100 unless requested otherwise`}
                          value={rules}
                          onChange={(e) => setRules(e.target.value)}
                          maxLength={5000}
                          disabled={isViewer}
                          className="min-h-[200px] bg-muted/20 border-border text-sm text-foreground font-mono rounded-xl p-4"
                        />
                        <div className="flex justify-end gap-3">
                          {!isViewer && (
                            <Button variant="outline" onClick={() => setRules("")} className="h-10 text-xs font-bold rounded-xl">
                              Clear Rules
                            </Button>
                          )}
                          {hasRulesChanges && !isViewer && (
                            <Button
                              className="h-10 text-xs font-bold rounded-xl px-6"
                              onClick={async () => {
                                if (selectedGraph?.id) {
                                  try {
                                    await DatabaseService.updateUserRules(selectedGraph.id, rules);
                                    loadedRulesRef.current = rules;
                                    toast({ title: "Rules saved", description: "SQL writing rules successfully saved." });
                                  } catch (error: any) {
                                    toast({ title: "Save failed", description: error.message, variant: "destructive" });
                                  }
                                }
                              }}
                            >
                              Save Rules
                            </Button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB: TEAM MANAGEMENT */}
          {activeTab === 'team' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                    Team Management
                    {!isAdmin && <ShieldAlert className="w-5 h-5 text-warning" />}
                  </h1>
                  <p className="text-sm text-muted-foreground mt-1">
                    {isAdmin ? "Manage team members, roles and account status." : "Only Admin accounts have access to this area."}
                  </p>
                </div>
                {isAdmin && (
                  <Button
                    onClick={() => { setShowCreateModal(true); setCreateError(''); }}
                    className="h-10 px-5 text-xs font-bold rounded-xl gap-2"
                  >
                    <UserPlus className="w-4 h-4" />
                    Add Member
                  </Button>
                )}
              </div>

              {/* Stats row */}
              {isAdmin && usersList.length > 0 && (
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: 'Total Members', value: usersList.length, icon: Users, color: 'text-primary', bg: 'bg-primary/10' },
                    { label: 'Active Accounts', value: usersList.filter(u => u.isActive).length, icon: CheckCircle2, color: 'text-success', bg: 'bg-success/10' },
                    { label: 'Inactive', value: usersList.filter(u => !u.isActive).length, icon: XCircle, color: 'text-muted-foreground', bg: 'bg-muted/20' },
                  ].map(({ label, value, icon: Icon, color, bg }) => (
                    <div key={label} className="bg-card border border-border rounded-2xl p-4 flex items-center gap-4">
                      <div className={cn('rounded-xl p-2.5', bg)}>
                        <Icon className={cn('w-5 h-5', color)} />
                      </div>
                      <div>
                        <p className="text-2xl font-extrabold">{value}</p>
                        <p className="text-xs text-muted-foreground font-medium">{label}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden">
                {!isAdmin ? (
                  <div className="h-[400px] flex flex-col items-center justify-center text-center p-6 text-muted-foreground/50">
                    <ShieldAlert className="w-16 h-16 opacity-20 mb-4 text-warning" />
                    <h3 className="font-bold text-lg text-foreground mb-1">Access Denied</h3>
                    <p className="text-sm max-w-[250px] mx-auto">Please login with an Administrator account to manage team members.</p>
                  </div>
                ) : isAdminLoading ? (
                  <div className="h-[300px] flex items-center justify-center gap-3">
                    <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    <span className="text-sm text-muted-foreground">Loading members...</span>
                  </div>
                ) : usersList.length === 0 ? (
                  <div className="h-[200px] flex flex-col items-center justify-center text-muted-foreground/50">
                    <Users className="w-12 h-12 opacity-20 mb-3" />
                    <p className="text-sm">No team members found.</p>
                    <Button variant="outline" className="mt-4 h-9 text-xs rounded-xl" onClick={() => setShowCreateModal(true)}>
                      <UserPlus className="w-4 h-4 mr-2" /> Add first member
                    </Button>
                  </div>
                ) : (
                  <div className="divide-y divide-border/50">
                    {/* Header */}
                    <div className="grid grid-cols-12 gap-4 px-5 py-3 bg-muted/20 text-xs font-bold text-muted-foreground uppercase tracking-wider">
                      <div className="col-span-5">Member</div>
                      <div className="col-span-3">Role</div>
                      <div className="col-span-2 text-center">Status</div>
                      <div className="col-span-2 text-right">Actions</div>
                    </div>
                    {usersList.map((u) => {
                      const isSelf = u.id === user?.id;
                      const roleConfig: Record<string, { label: string; icon: any; class: string }> = {
                        admin: { label: 'Admin', icon: Shield, class: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400' },
                        analyst: { label: 'Analyst', icon: BarChart3, class: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400' },
                        viewer: { label: 'Viewer', icon: Eye, class: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' },
                      };
                      const rc = roleConfig[u.role] || roleConfig.viewer;
                      const RoleIcon = rc.icon;
                      return (
                        <div key={u.id} className="grid grid-cols-12 gap-4 px-5 py-4 items-center hover:bg-muted/10 transition-colors">
                          {/* Avatar + Info */}
                          <div className="col-span-5 flex items-center gap-3 min-w-0">
                            <div className="w-9 h-9 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary font-bold text-sm shrink-0">
                              {(u.firstName?.[0] || '?').toUpperCase()}
                            </div>
                            <div className="flex flex-col min-w-0">
                              <span className="text-sm font-semibold text-foreground truncate flex items-center gap-2">
                                {u.firstName} {u.lastName}
                                {isSelf && <Badge variant="outline" className="text-[10px] py-0 h-4 border-primary/30 text-primary">You</Badge>}
                              </span>
                              <span className="text-xs text-muted-foreground truncate">{u.email}</span>
                            </div>
                          </div>

                          {/* Role selector */}
                          <div className="col-span-3">
                            <Select
                              value={u.role}
                              disabled={isSelf || updatingUserId === u.id}
                              onValueChange={(val) => handleUpdateUser(u.id, val, u.isActive)}
                            >
                              <SelectTrigger className="h-9 w-[130px] bg-background border-border text-xs rounded-xl">
                                <div className="flex items-center gap-1.5">
                                  <RoleIcon className="w-3.5 h-3.5" />
                                  <SelectValue />
                                </div>
                              </SelectTrigger>
                              <SelectContent className="rounded-xl border-border">
                                <SelectItem value="admin"><span className="flex items-center gap-2"><Shield className="w-3.5 h-3.5 text-rose-500" />Admin</span></SelectItem>
                                <SelectItem value="analyst"><span className="flex items-center gap-2"><BarChart3 className="w-3.5 h-3.5 text-sky-500" />Analyst</span></SelectItem>
                                <SelectItem value="viewer"><span className="flex items-center gap-2"><Eye className="w-3.5 h-3.5 text-emerald-500" />Viewer</span></SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          {/* Active toggle */}
                          <div className="col-span-2 flex items-center justify-center gap-2">
                            {updatingUserId === u.id ? (
                              <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                            ) : (
                              <Switch
                                checked={u.isActive}
                                disabled={isSelf}
                                onCheckedChange={(checked) => handleUpdateUser(u.id, u.role, checked)}
                                title={u.isActive ? 'Click to deactivate' : 'Click to activate'}
                              />
                            )}
                          </div>

                          {/* Delete */}
                          <div className="col-span-2 flex justify-end">
                            {!isSelf && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg"
                                onClick={() => handleDeleteUser(u)}
                                disabled={deletingUserId === u.id}
                                title="Remove member"
                              >
                                {deletingUserId === u.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserX className="w-4 h-4" />}
                              </Button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Refresh button */}
              {isAdmin && (
                <div className="flex justify-end">
                  <Button variant="ghost" className="h-9 text-xs text-muted-foreground gap-2 rounded-xl" onClick={fetchUsers} disabled={isAdminLoading}>
                    <RefreshCw className={cn('w-3.5 h-3.5', isAdminLoading && 'animate-spin')} />
                    Refresh
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Create User Modal */}
          <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
            <DialogContent className="rounded-2xl border-border max-w-md">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-lg">
                  <UserPlus className="w-5 h-5 text-primary" />
                  Add New Member
                </DialogTitle>
                <DialogDescription>Create a new account and add them to your team.</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-bold">First Name *</Label>
                    <Input value={createForm.firstName} onChange={e => setCreateForm(f => ({ ...f, firstName: e.target.value }))} placeholder="John" className="h-9 rounded-xl text-sm" />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-bold">Last Name</Label>
                    <Input value={createForm.lastName} onChange={e => setCreateForm(f => ({ ...f, lastName: e.target.value }))} placeholder="Doe" className="h-9 rounded-xl text-sm" />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Email *</Label>
                  <Input type="email" value={createForm.email} onChange={e => setCreateForm(f => ({ ...f, email: e.target.value }))} placeholder="john@company.com" className="h-9 rounded-xl text-sm" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Password *</Label>
                  <Input type="password" value={createForm.password} onChange={e => setCreateForm(f => ({ ...f, password: e.target.value }))} placeholder="Min. 8 characters" className="h-9 rounded-xl text-sm" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Role</Label>
                  <Select value={createForm.role} onValueChange={val => setCreateForm(f => ({ ...f, role: val }))}>
                    <SelectTrigger className="h-9 rounded-xl text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="rounded-xl">
                      <SelectItem value="admin">Admin — Full access</SelectItem>
                      <SelectItem value="analyst">Analyst — Query & analyze</SelectItem>
                      <SelectItem value="viewer">Viewer — Read only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {createError && (
                  <div className="flex items-center gap-2 text-xs text-destructive bg-destructive/10 rounded-xl px-3 py-2">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    {createError}
                  </div>
                )}
              </div>
              <DialogFooter className="gap-2">
                <Button variant="ghost" className="rounded-xl" onClick={() => setShowCreateModal(false)}>Cancel</Button>
                <Button onClick={handleCreateUser} disabled={isCreating} className="rounded-xl gap-2">
                  {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
                  Create Account
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Delete Confirm Dialog */}
          <Dialog open={!!confirmDeleteUser} onOpenChange={(open) => !open && setConfirmDeleteUser(null)}>
            <DialogContent className="rounded-2xl border-border max-w-sm">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-destructive">
                  <AlertTriangle className="w-5 h-5" />
                  Remove Member
                </DialogTitle>
                <DialogDescription>
                  Are you sure you want to remove <strong>{confirmDeleteUser?.firstName} {confirmDeleteUser?.lastName}</strong> ({confirmDeleteUser?.email})? This action cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter className="gap-2">
                <Button variant="ghost" className="rounded-xl" onClick={() => setConfirmDeleteUser(null)}>Cancel</Button>
                <Button variant="destructive" onClick={confirmDelete} disabled={!!deletingUserId} className="rounded-xl gap-2">
                  {deletingUserId ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  Remove
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* TAB: DEVELOPER */}
          {activeTab === 'dev' && (
            <div className="space-y-8">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Developer / Tokens</h1>
                <p className="text-sm text-muted-foreground mt-1">Manage API integrations and Model Context Protocol (MCP) settings.</p>
              </div>

              <div className="bg-card border border-border rounded-2xl p-6 shadow-sm space-y-6">
                <div className="flex items-center justify-between border-b border-border/50 pb-4">
                  <div className="flex items-center gap-2">
                    <Code className="w-5 h-5 text-primary" />
                    <h3 className="text-base font-bold">Personal Access Tokens</h3>
                  </div>
                  <Button onClick={handleGenerateToken} className="h-9 text-xs rounded-xl font-bold px-4">
                    Generate New Token
                  </Button>
                </div>
                
                {newToken && (
                  <div className="bg-success/10 border border-success/30 p-4 rounded-xl flex items-center justify-between">
                    <div>
                      <p className="text-xs font-bold text-success mb-1">New Token Generated</p>
                      <code className="text-success font-mono text-sm break-all">{newToken}</code>
                    </div>
                    <Button variant="outline" className="h-9 ml-4 shrink-0 rounded-xl bg-background" onClick={() => {
                      navigator.clipboard.writeText(newToken);
                      toast({ title: "Copied to clipboard" });
                    }}>
                      <Copy className="w-4 h-4 mr-2" /> Copy
                    </Button>
                  </div>
                )}
                
                <div className="space-y-3">
                  <Label className="text-sm font-bold text-foreground">Active Tokens</Label>
                  {isTokensLoading ? (
                    <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
                  ) : tokens.length === 0 ? (
                    <div className="text-center text-muted-foreground/60 py-8 border-2 border-dashed border-border rounded-xl text-sm">
                      No active tokens found.
                    </div>
                  ) : (
                    <div className="divide-y divide-border/50 border border-border/50 rounded-xl overflow-hidden">
                      {tokens.map(t => (
                        <div key={t.token_id} className="flex items-center justify-between p-4 bg-muted/10 hover:bg-muted/20 transition-colors">
                          <div className="flex flex-col">
                            <span className="font-mono text-sm text-foreground">{t.token_id.substring(0, 12)}••••••••</span>
                            <span className="text-xs text-muted-foreground">Generated Token</span>
                          </div>
                          <Button variant="ghost" className="h-9 w-9 p-0 text-destructive hover:text-destructive hover:bg-destructive/10 rounded-xl" onClick={() => handleDeleteToken(t.token_id)}>
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="bg-card border border-border rounded-2xl p-6 shadow-sm space-y-6">
                <div className="flex items-center gap-2 border-b border-border/50 pb-4">
                  <Sparkles className="w-5 h-5 text-primary" />
                  <h3 className="text-base font-bold">MCP Server Integration</h3>
                </div>
                
                <Alert className="bg-primary/5 text-primary border-none rounded-xl">
                  <AlertDescription className="text-sm font-medium leading-relaxed">
                    Connect StrongBI directly to Cursor, Windsurf, or other AI IDEs using the Model Context Protocol. Add the JSON below to your IDE's MCP config.
                  </AlertDescription>
                </Alert>

                <div className="bg-[#0f172a] text-slate-300 rounded-xl p-6 font-mono text-sm overflow-x-auto">
                  <pre>{`{
  "mcpServers": {
    "strongbi": {
      "command": "python",
      "args": [
        "-m",
        "strongbi.mcp_server",
        "--url",
        "${window.location.origin}",
        "--token",
        "${newToken || 'YOUR_API_TOKEN'}"
      ]
    }
  }
}`}</pre>
                </div>
                
                <div className="flex justify-end">
                  <Button 
                    variant="outline" 
                    className="h-10 text-xs font-bold border-border rounded-xl"
                    onClick={() => {
                      navigator.clipboard.writeText(`{
  "mcpServers": {
    "strongbi": {
      "command": "python",
      "args": ["-m", "strongbi.mcp_server", "--url", "${window.location.origin}", "--token", "${newToken || 'YOUR_API_TOKEN'}"]
    }
  }
}`);
                      toast({ title: "Copied MCP Config to clipboard" });
                    }}
                  >
                    <Copy className="w-4 h-4 mr-2" /> Copy Configuration
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* TAB: SYSTEM INFO */}
          {activeTab === 'system' && (
            <div className="space-y-8">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">System Info</h1>
                <p className="text-sm text-muted-foreground mt-1">Backend environment details and database engine status.</p>
              </div>

              <div className="bg-card border border-border rounded-2xl p-6 shadow-sm space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-muted/20 border border-border/50 rounded-2xl p-5 space-y-2">
                    <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Graph Engine</p>
                    <p className="text-xl font-extrabold flex items-center gap-2">
                      <Badge className={cn("text-xs py-1 px-3 border-none", systemInfo?.graphDbType === 'Neo4j' ? 'bg-orange-100 text-orange-700' : 'bg-primary/20 text-primary')}>
                        {systemInfo?.graphDbType || "Scanning..."}
                      </Badge>
                    </p>
                  </div>
                  <div className="bg-muted/20 border border-border/50 rounded-2xl p-5 space-y-2">
                    <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Default LLM Provider</p>
                    <p className="text-xl font-extrabold text-foreground uppercase tracking-tight">
                      {systemInfo?.defaultLlmProvider || "Scanning..."}
                    </p>
                  </div>
                </div>

                <div className="bg-primary/5 rounded-2xl border border-primary/10 p-6 space-y-4">
                  <h4 className="font-bold text-sm text-foreground flex items-center gap-2">
                    <HelpCircle className="w-4 h-4 text-primary" />
                    How to modify backend behavior
                  </h4>
                  <div className="space-y-4 text-sm text-muted-foreground">
                    <div>
                      <p className="font-semibold text-foreground mb-1">1. Changing Graph Database Engine</p>
                      <p>The system automatically uses <b>Neo4j</b> if <code>NEO4J_URL</code> is configured in the <code>.env</code> file of the backend. Otherwise, it defaults to <b>FalkorDB</b>.</p>
                    </div>
                    <div>
                      <p className="font-semibold text-foreground mb-1">2. Local LLM Server (vLLM / Ollama)</p>
                      <p>Set <code>VLLM_MODEL</code> and <code>VLLM_API_BASE</code> in the <code>.env</code> file to route all default generation through a self-hosted engine.</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default V2Settings;
