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
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { 
  Settings, Users, Key, ShieldAlert, Code, Trash2, Copy, 
  Loader2, Cpu, Sliders, CheckCircle2, XCircle,
  UserPlus, Shield, Eye, BarChart3, AlertTriangle, CpuIcon, Network, KeyRound, Server, Plus
} from "lucide-react";
import { useApiKeyValidation } from "@/hooks/useApiKeyValidation";
import { AI_VENDORS, getVendorConfig, DEFAULT_MODEL } from "@/utils/vendorConfig";

type Tab = "ai" | "team" | "dev" | "system";

const V4Settings = () => {
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
  const currentGraphIdRef = useRef<string | null>(null);

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
    if (activeTab === "dev") fetchTokens();
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
        setRules('');
        loadedRulesRef.current = '';
        return;
      }

      setIsLoadingRules(true);
      try {
        const dbRules = await DatabaseService.getUserRules(selectedGraph.id);
        const rulesText = dbRules || '';
        setRules(rulesText);
        loadedRulesRef.current = rulesText;
        setInitialRulesLoaded(true);
      } catch (error) {
        console.error("Failed to load rules:", error);
        setRules('');
        loadedRulesRef.current = '';
      } finally {
        setIsLoadingRules(false);
      }
    };

    loadRules();
  }, [selectedGraph, useRulesFromDatabase]);

  useEffect(() => {
    localStorage.setItem('queryweaver_use_memory', useMemory.toString());
  }, [useMemory]);

  useEffect(() => {
    localStorage.setItem('queryweaver_use_rules_from_database', useRulesFromDatabase.toString());
  }, [useRulesFromDatabase]);

  useEffect(() => {
    if (tempVendor !== vendor) {
      const conf = getVendorConfig(tempVendor);
      setTempModelName(conf?.defaultModel || DEFAULT_MODEL);
      setTempApiKey("");
      setTempApiBase("");
    }
  }, [tempVendor, vendor]);

  const handleSaveApiKey = async () => {
    if (!tempModelName.trim()) {
      toast({ title: "Model Required", description: "Please specify a model name.", variant: "destructive" });
      return;
    }

    if (!tempApiKey.trim() && tempVendor !== 'vllm' && tempVendor !== 'ollama' && !tempApiBase.trim()) {
      toast({ title: "API Key Required", description: "Please enter an API key for this provider.", variant: "destructive" });
      return;
    }

    const isValid = await validateApiKey(tempVendor, tempApiKey, tempModelName, tempApiBase);
    
    if (isValid) {
      setVendor(tempVendor);
      setApiKey(tempApiKey);
      setModelName(tempModelName);
      setCustomEndpoint(tempApiBase);
      setIsApiKeyValid(true);
      toast({ title: "Configuration Saved", description: "Your AI configuration has been verified and saved." });
    } else {
      setIsApiKeyValid(false);
    }
  };

  const handleClearApiKey = () => {
    clearSettings();
    setTempApiKey("");
    setTempModelName(DEFAULT_MODEL);
    setTempApiBase("");
    clearValidation();
    toast({ title: "Settings Cleared", description: "API Key and Custom Endpoint removed." });
  };

  const fetchUsers = async () => {
    setIsAdminLoading(true);
    try {
      const list = await AuthService.listUsers();
      setUsersList(list);
    } catch (e: any) {
      toast({ title: "Error fetching users", description: e.message, variant: "destructive" });
    } finally {
      setIsAdminLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "team" && isAdmin) fetchUsers();
  }, [activeTab, isAdmin]);

  const handleUpdateRole = async (userId: string, newRole: string) => {
    if (userId === user?.id) {
      toast({ title: "Invalid Action", description: "You cannot change your own role.", variant: "destructive" });
      return;
    }
    setUpdatingUserId(userId);
    try {
      await AuthService.updateUser(userId, { role: newRole });
      toast({ title: "Role updated", description: "User permissions have been updated successfully." });
      fetchUsers();
    } catch (error: any) {
      toast({ title: "Update failed", description: error.message, variant: "destructive" });
    } finally {
      setUpdatingUserId(null);
    }
  };

  const handleDeleteUser = async (u: any) => setConfirmDeleteUser(u);

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
    <div className="flex w-full h-full overflow-hidden bg-[#fafafa] dark:bg-[#09090b] font-sans">
      
      {/* V4 Sidebar Navigation for Settings */}
      <div className="w-64 border-r border-gray-200 dark:border-gray-800 shrink-0 flex flex-col bg-white dark:bg-black/50 p-6 z-10 shadow-sm">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg">
            <Settings className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">Settings</h1>
            <p className="text-[10px] text-gray-500 font-medium uppercase tracking-wider">Preferences</p>
          </div>
        </div>

        <div className="space-y-2">
          <button
            className={cn("w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm", activeTab === 'ai' ? "bg-primary/10 text-primary font-bold shadow-sm" : "text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800")}
            onClick={() => setActiveTab('ai')}
          >
            <CpuIcon className="w-4 h-4" /> AI Configuration
          </button>
          
          <button
            className={cn("w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm", activeTab === 'team' ? "bg-primary/10 text-primary font-bold shadow-sm" : "text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800")}
            onClick={() => setActiveTab('team')}
          >
            <Users className="w-4 h-4" /> Team Management
          </button>

          <button
            className={cn("w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm", activeTab === 'dev' ? "bg-primary/10 text-primary font-bold shadow-sm" : "text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800")}
            onClick={() => setActiveTab('dev')}
          >
            <Code className="w-4 h-4" /> API Tokens
          </button>

          <button
            className={cn("w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm", activeTab === 'system' ? "bg-primary/10 text-primary font-bold shadow-sm" : "text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800")}
            onClick={() => setActiveTab('system')}
          >
            <Server className="w-4 h-4" /> System Info
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-8 lg:p-12 relative">
        <div className="max-w-4xl mx-auto space-y-8">
          
          {/* TAB: AI CONFIGURATION */}
          {activeTab === 'ai' && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div className="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-3xl p-8 shadow-sm space-y-8 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl -z-10" />
                
                <div className="flex items-center gap-3 border-b border-gray-100 dark:border-gray-800 pb-6">
                  <div className="p-3 bg-primary/10 text-primary rounded-xl"><KeyRound className="w-5 h-5" /></div>
                  <div>
                    <h3 className="text-xl font-bold">API Credentials</h3>
                    <p className="text-sm text-gray-500">Configure your primary AI provider and models.</p>
                  </div>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="space-y-3">
                    <Label className="text-sm font-bold text-gray-700 dark:text-gray-300">Provider (Vendor)</Label>
                    <Select value={tempVendor} onValueChange={(val) => setTempVendor(val as AIVendor)}>
                      <SelectTrigger className="h-12 rounded-xl bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700">
                        <SelectValue placeholder="Select Vendor" />
                      </SelectTrigger>
                      <SelectContent className="rounded-xl border-gray-200 dark:border-gray-700">
                        {AI_VENDORS.map((v) => (
                          <SelectItem key={v.value} value={v.value}>{v.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-3">
                    <Label className="text-sm font-bold text-gray-700 dark:text-gray-300">Model Name</Label>
                    <Input 
                      value={tempModelName} 
                      onChange={(e) => setTempModelName(e.target.value)}
                      placeholder={getVendorConfig(tempVendor)?.exampleModel || "gpt-4"}
                      disabled={!tempApiKey.trim() && tempVendor !== 'vllm' && tempVendor !== 'ollama' && !tempApiBase.trim()}
                      className="h-12 rounded-xl bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700"
                    />
                  </div>
                </div>

                {['vllm', 'ollama', 'openai', 'azure', 'anthropic', 'cohere'].includes(tempVendor) && (
                  <div className="space-y-3">
                    <Label className="text-sm font-bold text-gray-700 dark:text-gray-300">API Base URL (Optional)</Label>
                    <Input 
                      value={tempApiBase} 
                      onChange={(e) => setTempApiBase(e.target.value)}
                      placeholder="e.g., http://localhost:11434"
                      className="h-12 rounded-xl bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700 font-mono text-sm"
                    />
                  </div>
                )}

                {(tempVendor === 'vllm' || tempVendor === 'ollama') ? (
                  <div className="bg-primary/10 border border-primary/20 rounded-xl p-4 text-sm text-primary">
                    <p className="font-bold flex items-center gap-2"><Settings className="w-4 h-4"/> Host Server Config Tip</p>
                    <p className="mt-1 opacity-90">Self-hosted models run locally. Configure URL above or via Backend ENV variables.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <Label className="text-sm font-bold text-gray-700 dark:text-gray-300">API Key</Label>
                    <Input 
                      type="password"
                      value={tempApiKey} 
                      onChange={(e) => { setTempApiKey(e.target.value); clearValidation(); }}
                      placeholder={getVendorConfig(tempVendor)?.keyPrefix ? `${getVendorConfig(tempVendor)?.keyPrefix}...` : "Enter API Key..."}
                      className="h-12 rounded-xl bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700"
                    />
                  </div>
                )}

                {validationMessage && (
                  <div className={cn("p-4 rounded-xl border flex items-center gap-2 text-sm font-semibold", validationStatus === 'error' ? 'bg-red-50 text-red-600 border-red-200 dark:bg-red-500/10 dark:border-red-500/20' : 'bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/20')}>
                    {validationStatus === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                    {validationMessage}
                  </div>
                )}

                <div className="flex justify-end gap-3 pt-6 border-t border-gray-100 dark:border-gray-800">
                  <Button variant="outline" onClick={handleClearApiKey} disabled={!apiKey && !tempApiKey} className="h-12 rounded-xl px-6">
                    Clear Key
                  </Button>
                  <Button onClick={handleSaveApiKey} disabled={isValidating || (!tempApiKey.trim() && tempVendor !== 'vllm' && tempVendor !== 'ollama') || !tempModelName.trim()} className="h-12 rounded-xl px-8 shadow-md">
                    {isValidating && <Loader2 className="mr-2 w-4 h-4 animate-spin" />}
                    Save Changes
                  </Button>
                </div>
              </div>

              {/* Preferences */}
              <div className="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-3xl p-8 shadow-sm space-y-6">
                <div className="flex items-center gap-3 border-b border-gray-100 dark:border-gray-800 pb-6">
                  <div className="p-3 bg-indigo-500/10 text-indigo-500 rounded-xl"><Sliders className="w-5 h-5" /></div>
                  <div>
                    <h3 className="text-xl font-bold">Preferences & Rules</h3>
                    <p className="text-sm text-gray-500">Fine-tune memory and query generation behaviors.</p>
                  </div>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-2xl p-5 flex justify-between items-center">
                    <div className="space-y-1">
                      <Label className="text-base font-bold">Use AI Memory</Label>
                      <p className="text-xs text-gray-500">Contextual awareness in chats.</p>
                    </div>
                    <Switch checked={useMemory} onCheckedChange={setUseMemory} />
                  </div>

                  <div className="bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-2xl p-5 flex justify-between items-center">
                    <div className="space-y-1">
                      <Label className="text-base font-bold">Custom DB Rules</Label>
                      <p className="text-xs text-gray-500">Apply rules per database.</p>
                    </div>
                    <Switch checked={useRulesFromDatabase} onCheckedChange={setUseRulesFromDatabase} />
                  </div>
                </div>

                {useRulesFromDatabase && (
                  <div className="space-y-4 pt-4">
                    <Label className="font-bold">Generation Rules (Markdown)</Label>
                    <Textarea
                      placeholder="- Always use ISO formats&#10;- Limit to 100 rows"
                      value={rules}
                      onChange={(e) => setRules(e.target.value)}
                      disabled={isViewer || !selectedGraph}
                      className="min-h-[200px] bg-gray-50 dark:bg-gray-800/50 rounded-2xl p-5 font-mono text-sm"
                    />
                    {!selectedGraph && <p className="text-xs text-amber-500">Select a Database in Workspace to load its rules.</p>}
                    {hasRulesChanges && !isViewer && selectedGraph && (
                      <div className="flex justify-end pt-2">
                        <Button className="h-11 rounded-xl px-6" onClick={async () => {
                          try {
                            await DatabaseService.updateUserRules(selectedGraph.id, rules);
                            loadedRulesRef.current = rules;
                            toast({ title: "Rules saved" });
                          } catch (e: any) { toast({ title: "Error", description: e.message, variant: "destructive" }); }
                        }}>Save Rules</Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB: TEAM MANAGEMENT */}
          {activeTab === 'team' && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div className="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-3xl p-8 shadow-sm">
                <div className="flex items-center justify-between mb-8">
                  <div className="flex items-center gap-3">
                    <div className="p-3 bg-blue-500/10 text-blue-500 rounded-xl"><Users className="w-5 h-5" /></div>
                    <div>
                      <h3 className="text-xl font-bold flex items-center gap-2">Team Management {!isAdmin && <ShieldAlert className="w-4 h-4 text-amber-500"/>}</h3>
                      <p className="text-sm text-gray-500">{isAdmin ? "Manage team members and roles." : "Admin access required."}</p>
                    </div>
                  </div>
                  {isAdmin && (
                    <Button onClick={() => setShowCreateModal(true)} className="rounded-full shadow-sm bg-blue-600 hover:bg-blue-700">
                      <UserPlus className="w-4 h-4 mr-2" /> Add User
                    </Button>
                  )}
                </div>

                {!isAdmin ? (
                  <div className="p-12 text-center bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-200 dark:border-gray-700">
                    <ShieldAlert className="w-12 h-12 text-amber-500 mx-auto mb-4" />
                    <h4 className="text-lg font-bold">Access Denied</h4>
                    <p className="text-gray-500">Contact an administrator to manage team members.</p>
                  </div>
                ) : isAdminLoading ? (
                  <div className="flex justify-center p-12"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>
                ) : (
                  <div className="border border-gray-100 dark:border-gray-800 rounded-2xl overflow-hidden">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-gray-50 dark:bg-gray-800/50">
                        <tr>
                          <th className="px-6 py-4 font-semibold text-gray-500">User</th>
                          <th className="px-6 py-4 font-semibold text-gray-500">Email</th>
                          <th className="px-6 py-4 font-semibold text-gray-500">Role</th>
                          <th className="px-6 py-4 font-semibold text-gray-500 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                        {usersList.map((u) => (
                          <tr key={u.id} className="hover:bg-gray-50 dark:hover:bg-gray-900/50">
                            <td className="px-6 py-4 font-medium">{u.firstName} {u.lastName}</td>
                            <td className="px-6 py-4 text-gray-500">{u.email}</td>
                            <td className="px-6 py-4">
                              <Select 
                                value={u.role.toLowerCase()} 
                                onValueChange={(val) => handleUpdateRole(u.id, val)}
                                disabled={u.id === user?.id || updatingUserId === u.id}
                              >
                                <SelectTrigger className="h-8 w-32 rounded-lg text-xs bg-transparent">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="admin">Admin</SelectItem>
                                  <SelectItem value="analyst">Analyst</SelectItem>
                                  <SelectItem value="viewer">Viewer</SelectItem>
                                </SelectContent>
                              </Select>
                            </td>
                            <td className="px-6 py-4 text-right">
                              <Button 
                                variant="ghost" 
                                size="icon" 
                                disabled={u.id === user?.id || deletingUserId === u.id}
                                onClick={() => handleDeleteUser(u)}
                                className="h-8 w-8 text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
                              >
                                {deletingUserId === u.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB: DEV / TOKENS */}
          {activeTab === 'dev' && (
            <div className="space-y-6 animate-in fade-in duration-300">
              <div className="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-3xl p-8 shadow-sm">
                <div className="flex items-center justify-between mb-8">
                  <div className="flex items-center gap-3">
                    <div className="p-3 bg-teal-500/10 text-teal-500 rounded-xl"><Code className="w-5 h-5" /></div>
                    <div>
                      <h3 className="text-xl font-bold flex items-center gap-2">API Tokens {!isAdmin && <ShieldAlert className="w-4 h-4 text-amber-500"/>}</h3>
                      <p className="text-sm text-gray-500">Generate personal access tokens for API integration.</p>
                    </div>
                  </div>
                  {isAdmin && (
                    <Button onClick={handleGenerateToken} className="rounded-full shadow-sm bg-teal-600 hover:bg-teal-700">
                      <Plus className="w-4 h-4 mr-2" /> Generate Token
                    </Button>
                  )}
                </div>

                {!isAdmin ? (
                   <div className="p-12 text-center bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-200 dark:border-gray-700">
                   <ShieldAlert className="w-12 h-12 text-amber-500 mx-auto mb-4" />
                   <h4 className="text-lg font-bold">Access Denied</h4>
                   <p className="text-gray-500">Only administrators can manage API tokens.</p>
                 </div>
                ) : (
                  <div className="space-y-6">
                    {newToken && (
                      <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-2xl p-6">
                        <h4 className="font-bold text-emerald-800 dark:text-emerald-300 mb-2">New Token Generated!</h4>
                        <p className="text-sm text-emerald-600 dark:text-emerald-400 mb-4">Please copy this token now. You will not be able to see it again.</p>
                        <div className="flex items-center gap-2">
                          <Input value={newToken} readOnly className="bg-white dark:bg-black font-mono text-sm" />
                          <Button onClick={() => { navigator.clipboard.writeText(newToken); toast({ title: "Copied!" }) }} variant="secondary">
                            <Copy className="w-4 h-4 mr-2"/> Copy
                          </Button>
                        </div>
                      </div>
                    )}

                    {isTokensLoading ? (
                      <div className="flex justify-center p-8"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>
                    ) : tokens.length === 0 ? (
                      <div className="text-center p-8 text-gray-500 border border-dashed rounded-xl">No active tokens found.</div>
                    ) : (
                      <div className="border border-gray-100 dark:border-gray-800 rounded-2xl overflow-hidden">
                        <table className="w-full text-sm text-left">
                          <thead className="bg-gray-50 dark:bg-gray-800/50">
                            <tr>
                              <th className="px-6 py-4 font-semibold text-gray-500">Token ID</th>
                              <th className="px-6 py-4 font-semibold text-gray-500">Created At</th>
                              <th className="px-6 py-4 font-semibold text-gray-500 text-right">Action</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                            {tokens.map((t) => (
                              <tr key={t.id} className="hover:bg-gray-50 dark:hover:bg-gray-900/50">
                                <td className="px-6 py-4 font-mono text-xs">{t.id}</td>
                                <td className="px-6 py-4 text-gray-500">{new Date(t.created_at).toLocaleString()}</td>
                                <td className="px-6 py-4 text-right">
                                  <Button variant="ghost" size="icon" onClick={() => handleDeleteToken(t.id)} className="text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10">
                                    <Trash2 className="w-4 h-4" />
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

        </div>
      </div>

      {/* Add User Modal */}
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent className="sm:max-w-[425px] rounded-[24px]">
          <DialogHeader>
            <DialogTitle>Add Team Member</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {createError && <p className="text-xs text-red-500 font-bold bg-red-50 p-3 rounded-xl">{createError}</p>}
            <div className="grid gap-2">
              <Label>First Name</Label>
              <Input value={createForm.firstName} onChange={e => setCreateForm({...createForm, firstName: e.target.value})} className="rounded-xl" />
            </div>
            <div className="grid gap-2">
              <Label>Last Name</Label>
              <Input value={createForm.lastName} onChange={e => setCreateForm({...createForm, lastName: e.target.value})} className="rounded-xl" />
            </div>
            <div className="grid gap-2">
              <Label>Email</Label>
              <Input type="email" value={createForm.email} onChange={e => setCreateForm({...createForm, email: e.target.value})} className="rounded-xl" />
            </div>
            <div className="grid gap-2">
              <Label>Password</Label>
              <Input type="password" value={createForm.password} onChange={e => setCreateForm({...createForm, password: e.target.value})} className="rounded-xl" />
            </div>
            <div className="grid gap-2">
              <Label>Role</Label>
              <Select value={createForm.role} onValueChange={(val) => setCreateForm({...createForm, role: val})}>
                <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="analyst">Analyst</SelectItem>
                  <SelectItem value="viewer">Viewer</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateModal(false)} className="rounded-full px-6">Cancel</Button>
            <Button onClick={handleCreateUser} disabled={isCreating} className="rounded-full px-8 shadow-sm">
              {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create User'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete User Confirm */}
      <Dialog open={!!confirmDeleteUser} onOpenChange={(open) => !open && setConfirmDeleteUser(null)}>
        <DialogContent className="sm:max-w-[400px] rounded-[24px]">
          <DialogHeader>
            <DialogTitle>Delete User</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove {confirmDeleteUser?.firstName} from the workspace? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <Button variant="outline" onClick={() => setConfirmDeleteUser(null)} className="rounded-full">Cancel</Button>
            <Button variant="destructive" onClick={confirmDelete} className="rounded-full px-6 bg-red-600 hover:bg-red-700">
              {deletingUserId ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Yes, Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
};

export default V4Settings;
