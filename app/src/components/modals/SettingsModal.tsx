import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useSettings, AIVendor } from "@/contexts/SettingsContext";
import { useAuth } from "@/contexts/AuthContext";
import { AuthService } from "@/services/auth";
import { useToast } from "@/hooks/use-toast";
import { Settings, Users, Key, ShieldAlert, Check, Loader2 } from "lucide-react";

interface SettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SettingsModal = ({ open, onOpenChange }: SettingsModalProps) => {
  const { vendor, apiKey, modelName, setVendor, setApiKey, setModelName } = useSettings();
  const { user } = useAuth();
  const { toast } = useToast();

  const [localVendor, setLocalVendor] = useState<AIVendor>(vendor);
  const [localApiKey, setLocalApiKey] = useState(apiKey || "");
  const [localModelName, setLocalModelName] = useState(modelName);

  // Admin states
  const [usersList, setUsersList] = useState<any[]>([]);
  const [isAdminLoading, setIsAdminLoading] = useState(false);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);

  const isAdmin = user?.role?.toLowerCase() === "admin";

  useEffect(() => {
    if (open) {
      setLocalVendor(vendor);
      setLocalApiKey(apiKey || "");
      setLocalModelName(modelName);

      if (isAdmin) {
        fetchUsers();
      }
    }
  }, [open, vendor, apiKey, modelName, isAdmin]);

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

  const handleSaveSettings = () => {
    setVendor(localVendor);
    setApiKey(localApiKey || null);
    setModelName(localModelName);
    toast({
      title: "Saved cài đặt",
      description: "Cấu hình AI đã được cập nhật thành công.",
    });
  };

  const handleUpdateUser = async (userId: string, role: string, isActive: boolean) => {
    setUpdatingUserId(userId);
    try {
      await AuthService.updateUser(userId, role, isActive);
      toast({
        title: "Update successful",
        description: "Member info has been updated.",
      });
      fetchUsers();
    } catch (error: any) {
      toast({
        title: "Update failed",
        description: error.message || "Could not update member info.",
        variant: "destructive",
      });
    } finally {
      setUpdatingUserId(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[650px] bg-card border border-border/80 shadow-2xl rounded-[32px] overflow-hidden p-0">
        <div className="relative pt-6 pb-4 px-6 bg-gradient-to-b from-primary/10 via-transparent to-transparent">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
          <DialogTitle className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary" />
            Cấu Hình Hệ Thống
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground mt-1">
            Thiết lập mô hình AI thông minh hoặc quản lý tài khoản thành viên trong doanh nghiệp.
          </DialogDescription>
        </div>

        <div className="px-6 pb-6">
          <Tabs defaultValue="ai" className="w-full">
            <TabsList className="grid w-full grid-cols-2 mb-6 bg-muted p-1 rounded-xl">
              <TabsTrigger value="ai" className="rounded-lg py-2 text-xs font-semibold">
                <Key className="w-3.5 h-3.5 mr-2" />
                Cài Đặt AI Agent
              </TabsTrigger>
              <TabsTrigger 
                value="admin" 
                disabled={!isAdmin} 
                className="rounded-lg py-2 text-xs font-semibold data-[state=active]:bg-card"
              >
                <Users className="w-3.5 h-3.5 mr-2" />
                Member Management
                {!isAdmin && <ShieldAlert className="w-3 h-3 ml-1.5 opacity-60" />}
              </TabsTrigger>
            </TabsList>

            {/* AI Settings Tab */}
            <TabsContent value="ai" className="space-y-4">
              <div className="space-y-2">
                <Label className="text-xs font-bold text-muted-foreground">Provider (Vendor)</Label>
                <Select value={localVendor} onValueChange={(val) => setLocalVendor(val as AIVendor)}>
                  <SelectTrigger className="h-11 rounded-xl bg-muted/40 border-border/80">
                    <SelectValue placeholder="Select Vendor" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="openai">OpenAI</SelectItem>
                    <SelectItem value="google">Google Gemini</SelectItem>
                    <SelectItem value="anthropic">Anthropic Claude</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label className="text-xs font-bold text-muted-foreground">Model Name (Model Name)</Label>
                <Input 
                  value={localModelName} 
                  onChange={(e) => setLocalModelName(e.target.value)}
                  placeholder="gpt-4o-mini hoặc gemini-1.5-flash"
                  className="h-11 rounded-xl bg-muted/40 border-border/80 text-foreground"
                />
              </div>

              <div className="space-y-2">
                <Label className="text-xs font-bold text-muted-foreground">API Key (Save tạm thời, không lưu trên disk)</Label>
                <Input 
                  type="password"
                  value={localApiKey} 
                  onChange={(e) => setLocalApiKey(e.target.value)}
                  placeholder="Nhập khóa API..."
                  className="h-11 rounded-xl bg-muted/40 border-border/80 text-foreground"
                />
              </div>

              <Button 
                onClick={handleSaveSettings}
                className="w-full mt-4 h-11 text-xs font-bold bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl"
              >
                Save Cài Đặt AI
              </Button>
            </TabsContent>

            {/* Admin User Management Tab */}
            <TabsContent value="admin" className="space-y-4">
              {isAdminLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                </div>
              ) : (
                <div className="border border-border/50 rounded-2xl overflow-hidden max-h-[300px] overflow-y-auto scrollbar-visible">
                  <table className="w-full text-xs text-left border-collapse">
                    <thead className="bg-muted sticky top-0 z-10 border-b border-border/50">
                      <tr>
                        <th className="px-4 py-3 font-semibold text-muted-foreground">Thành Viên</th>
                        <th className="px-4 py-3 font-semibold text-muted-foreground">Role (Role)</th>
                        <th className="px-4 py-3 font-semibold text-muted-foreground">Hoạt Động</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usersList.map((u) => {
                        const isSelf = u.id === user?.id;
                        return (
                          <tr key={u.id} className="border-b border-border/50 hover:bg-muted/10">
                            <td className="px-4 py-3">
                              <div className="flex flex-col">
                                <span className="font-bold text-foreground">
                                  {u.firstName} {u.lastName} {isSelf && "(You)"}
                                </span>
                                <span className="text-[10px] text-muted-foreground">{u.email}</span>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <Select
                                value={u.role}
                                disabled={isSelf || updatingUserId === u.id}
                                onValueChange={(val) => handleUpdateUser(u.id, val, u.isActive)}
                              >
                                <SelectTrigger className="h-8 w-28 bg-muted/40 border-border/50 text-[11px] rounded-lg">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="admin">Admin</SelectItem>
                                  <SelectItem value="analyst">Analyst</SelectItem>
                                  <SelectItem value="viewer">Viewer</SelectItem>
                                </SelectContent>
                              </Select>
                            </td>
                            <td className="px-4 py-3">
                              <Switch
                                checked={u.isActive}
                                disabled={isSelf || updatingUserId === u.id}
                                onCheckedChange={(checked) => handleUpdateUser(u.id, u.role, checked)}
                              />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SettingsModal;
