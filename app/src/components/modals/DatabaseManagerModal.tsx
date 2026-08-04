import React, { useRef, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useDatabase } from "@/contexts/DatabaseContext";
import { useToast } from "@/hooks/use-toast";
import { Database, Trash2, Upload, Plus, Eye, Check } from "lucide-react";
import DatabaseModal from "./DatabaseModal";

interface DatabaseManagerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onViewSchema: () => void;
}

const DatabaseManagerModal = ({ open, onOpenChange, onViewSchema }: DatabaseManagerModalProps) => {
  const { graphs, selectedGraph, selectGraph, uploadSchema, deleteGraph, isLoading } = useDatabase();
  const { toast } = useToast();
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      await uploadSchema(file, file.name.split('.')[0]);
      toast({
        title: "Tải Schema thành công",
        description: `Đã biên dịch thành công cấu trúc dữ liệu cho "${file.name}"`,
      });
    } catch (error: any) {
      toast({
        title: "Tải lên thất bại",
        description: error.message || "Không thể tải lên cấu trúc dữ liệu",
        variant: "destructive",
      });
    }
  };

  const handleDelete = async (graphId: string, name: string) => {
    if (!confirm(`Are you sure muốn xóa cấu trúc dữ liệu "${name}" không?`)) return;
    setIsDeleting(graphId);
    try {
      await deleteGraph(graphId);
      toast({
        title: "Đã xóa thành công",
        description: `Đã loại bỏ cấu trúc dữ liệu "${name}" khỏi hệ thống.`,
      });
    } catch (error: any) {
      toast({
        title: "Delete thất bại",
        description: error.message || "Không thể xóa cấu trúc dữ liệu",
        variant: "destructive",
      });
    } finally {
      setIsDeleting(null);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[550px] bg-card border border-border/80 shadow-2xl rounded-[32px] overflow-hidden p-6">
          <DialogHeader className="space-y-2 pb-4 border-b border-border/30">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-xl bg-primary/10 text-primary">
                <Database className="w-5 h-5" />
              </div>
              <DialogTitle className="text-xl font-bold tracking-tight text-foreground">
                Quản Lý Nguồn Dữ Liệu
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground text-left">
              Kết nối hoặc tải lên cấu trúc cơ sở dữ liệu của bạn để AI tiến hành phân tích and truy vấn.
            </DialogDescription>
          </DialogHeader>

          {/* Database List */}
          <div className="space-y-3 my-6 max-h-[300px] overflow-y-auto pr-1 scrollbar-visible">
            {graphs.length === 0 ? (
              <div className="text-center py-8 border-2 border-dashed border-border/50 rounded-2xl text-muted-foreground">
                <Database className="w-12 h-12 mx-auto mb-2 opacity-20" />
                <p className="text-sm font-medium">Chưa có nguồn dữ liệu nào được kết nối</p>
                <p className="text-xs opacity-60">Hãy tải file schema lên hoặc kết nối database mới.</p>
              </div>
            ) : (
              graphs.map((graph) => {
                const isSelected = selectedGraph?.id === graph.id;
                return (
                  <div
                    key={graph.id}
                    className={`flex items-center justify-between p-3.5 rounded-2xl border transition-all cursor-pointer ${
                      isSelected
                        ? "bg-primary/5 border-primary/40 shadow-sm"
                        : "bg-muted/10 border-border/50 hover:bg-muted/20"
                    }`}
                    onClick={() => selectGraph(graph.id)}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-xl ${isSelected ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground'}`}>
                        <Database className="w-4 h-4" />
                      </div>
                      <div className="flex flex-col items-start">
                        <span className="text-sm font-bold text-foreground flex items-center gap-1.5">
                          {graph.name}
                          {graph.isDemo && (
                            <Badge className="bg-sky-100 text-sky-700 hover:bg-sky-100 border-none text-[9px] px-1.5 py-0">Demo</Badge>
                          )}
                        </span>
                        <span className="text-[10px] text-muted-foreground font-medium">
                          Loại database: FalkorDB (Graph)
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      {isSelected && (
                        <div className="w-6 h-6 rounded-full bg-success/20 text-success flex items-center justify-center mr-2">
                          <Check className="w-3.5 h-3.5" />
                        </div>
                      )}
                      
                      <Button
                        variant="ghost"
                        size="icon"
                        className="w-8 h-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
                        onClick={onViewSchema}
                        title="View Schema Graph"
                      >
                        <Eye className="w-4 h-4" />
                      </Button>

                      {!graph.isDemo && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="w-8 h-8 rounded-lg text-destructive hover:text-destructive hover:bg-destructive/10"
                          disabled={isDeleting === graph.id}
                          onClick={() => handleDelete(graph.id, graph.name)}
                          title="Delete cấu trúc này"
                        >
                          {isDeleting === graph.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-2 gap-3 border-t border-border/30 pt-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".sql,.csv,.json"
              onChange={handleFileSelect}
              style={{ display: "none" }}
            />
            <Button
              variant="outline"
              className="rounded-xl h-11 border-border/70 hover:border-border hover:bg-muted font-bold text-xs"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
            >
              <Upload className="w-4 h-4 mr-2" />
              Tải File Schema
            </Button>
            <Button
              className="rounded-xl h-11 font-bold text-xs bg-primary hover:bg-primary/90 text-primary-foreground"
              onClick={() => setShowConnectModal(true)}
              disabled={isLoading}
            >
              <Plus className="w-4 h-4 mr-2" />
              Kết Nối Database
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Connection Modal */}
      <DatabaseModal open={showConnectModal} onOpenChange={setShowConnectModal} />
    </>
  );
};

export default DatabaseManagerModal;
