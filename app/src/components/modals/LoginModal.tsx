import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { Loader2, Mail, Lock, User, Sparkles } from "lucide-react";

interface LoginModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  canClose?: boolean;
}

const LoginModal = ({ open, onOpenChange, canClose = true }: LoginModalProps) => {
  const [activeTab, setActiveTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const { login, register } = useAuth();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || (activeTab === "register" && !name)) {
      toast({ title: "Error", description: "Please fill in all fields", variant: "destructive" });
      return;
    }
    
    setIsSubmitting(true);
    try {
      if (activeTab === "login") {
        await login.local(email, password);
        toast({ title: "Welcome back!", description: "Successfully logged in." });
        if (canClose) onOpenChange(false);
      } else {
        const [firstName, ...lastNames] = name.split(" ");
        const lastName = lastNames.join(" ") || "";
        await register(firstName, lastName, email, password);
        toast({ title: "Account created", description: "Successfully registered and logged in." });
        if (canClose) onOpenChange(false);
      }
    } catch (error: any) {
      toast({ 
        title: "Authentication Failed", 
        description: error.message || "An error occurred during authentication", 
        variant: "destructive" 
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={canClose ? onOpenChange : undefined}>
      <DialogContent
        className="sm:max-w-[440px] bg-card border border-border/80 shadow-2xl rounded-[32px] overflow-hidden p-0"
        onInteractOutside={(e) => { if (!canClose) e.preventDefault(); }}
        onEscapeKeyDown={(e) => { if (!canClose) e.preventDefault(); }}
      >
        {/* Beautiful Header Gradient */}
        <div className="relative pt-8 pb-4 px-6 text-center bg-gradient-to-b from-primary/10 via-transparent to-transparent">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
          
          <div className="mx-auto w-14 h-14 bg-gradient-to-tr from-primary to-primary-hover rounded-2xl flex items-center justify-center mb-3 shadow-md shadow-primary/20">
            <Sparkles className="w-6 h-6 text-primary-foreground" />
          </div>
          
          <DialogTitle className="text-2xl font-bold text-foreground tracking-tight">
            LDK StrongBI
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground mt-1 max-w-[280px] mx-auto">
            Hệ thống phân tích dữ liệu doanh nghiệp thông minh. Đăng nhập để tiếp tục.
          </DialogDescription>
        </div>

        <div className="p-6 pt-0">
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full">
            <TabsList className="grid w-full grid-cols-2 mb-6 bg-muted p-1 rounded-xl">
              <TabsTrigger 
                value="login" 
                className="rounded-lg py-2 text-sm font-semibold transition-all data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm text-muted-foreground"
              >
                Sign In
              </TabsTrigger>
              <TabsTrigger 
                value="register"
                className="rounded-lg py-2 text-sm font-semibold transition-all data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm text-muted-foreground"
              >
                Đăng Ký
              </TabsTrigger>
            </TabsList>
            
            <form onSubmit={handleSubmit} className="space-y-4">
              {activeTab === "register" && (
                <div className="space-y-2">
                  <Label htmlFor="name" className="text-xs font-semibold text-muted-foreground">Họ and Tên</Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/75 z-10" />
                    <Input 
                      id="name" 
                      placeholder="Nguyễn Văn A" 
                      className="pl-10 h-11 bg-muted border-border text-foreground placeholder:text-muted-foreground/40 font-medium focus-visible:ring-primary rounded-xl transition-all"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      disabled={isSubmitting}
                      required
                    />
                  </div>
                </div>
              )}
              
              <div className="space-y-2">
                <Label htmlFor="email" className="text-xs font-semibold text-muted-foreground">Địa chỉ Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/75 z-10" />
                  <Input 
                    id="email" 
                    type="email" 
                    placeholder="name@company.com" 
                    className="pl-10 h-11 bg-muted border-border text-foreground placeholder:text-muted-foreground/40 font-medium focus-visible:ring-primary rounded-xl transition-all"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isSubmitting}
                    required
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="password" className="text-xs font-semibold text-muted-foreground">Mật khẩu</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/75 z-10" />
                  <Input 
                    id="password" 
                    type="password" 
                    placeholder="••••••••" 
                    className="pl-10 h-11 bg-muted border-border text-foreground placeholder:text-muted-foreground/40 font-medium focus-visible:ring-primary rounded-xl transition-all"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isSubmitting}
                    required
                  />
                </div>
              </div>

              <Button 
                type="submit" 
                className="w-full mt-6 h-11 text-sm font-bold shadow-md rounded-xl transition-all duration-200 active:scale-[0.98] hover:shadow-lg bg-primary hover:bg-primary/90 text-primary-foreground"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  activeTab === "login" ? "Sign In" : "Tạo Tài Khoản"
                )}
              </Button>
            </form>

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border/80"></div>
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-card px-2 text-muted-foreground font-medium">Hoặc tiếp tục với</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Button 
                type="button" 
                variant="outline" 
                className="h-10 rounded-xl bg-card border-border/80 hover:bg-muted font-semibold text-xs"
                onClick={() => login.google()}
                disabled={isSubmitting}
              >
                <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                Google
              </Button>
              <Button 
                type="button" 
                variant="outline" 
                className="h-10 rounded-xl bg-card border-border/80 hover:bg-muted font-semibold text-xs"
                onClick={() => login.github()}
                disabled={isSubmitting}
              >
                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 24 24">
                  <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                </svg>
                GitHub
              </Button>
            </div>
          </Tabs>

          <div className="text-center text-[10px] text-muted-foreground/60 mt-6 pb-2">
            <p>Bằng việc đăng nhập, bạn đồng ý với Điều khoản của StrongBI</p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default LoginModal;
