import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChevronLeft, Save, Plus, Trash2, Edit2, Code, LayoutList, Network, Loader2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { buildApiUrl } from '@/config/api';
import { csrfHeaders } from '@/lib/csrf';

interface SemanticItem {
  name: string;
  type: string;
  description: string;
  expr?: string;
  sql?: string;
}

const V4Semantic = () => {
  const { graphId } = useParams<{ graphId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [schemaData, setSchemaData] = useState<any>(null);
  
  const [dimensions, setDimensions] = useState<SemanticItem[]>([]);
  const [metrics, setMetrics] = useState<SemanticItem[]>([]);
  const [jsonText, setJsonText] = useState("");

  const [editItem, setEditItem] = useState<{type: 'dimension'|'metric', index: number | null, data: SemanticItem} | null>(null);

  useEffect(() => {
    fetchSchema();
  }, [graphId]);

  const fetchSchema = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(buildApiUrl(`/graphs/${graphId}/semantic`), {
        credentials: 'include'
      });
      if (!response.ok) throw new Error("Lỗi tải cấu trúc ngữ nghĩa");
      const data = await response.json();
      
      setSchemaData(data);
      const config = data || {};
      setDimensions(config.dimensions || []);
      setMetrics(config.metrics || []);
      setJsonText(JSON.stringify({ dimensions: config.dimensions || [], metrics: config.metrics || [] }, null, 2));
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (source: 'visual' | 'json') => {
    setIsSaving(true);
    try {
      let payload = {};
      if (source === 'json') {
        payload = JSON.parse(jsonText);
      } else {
        payload = {
          dimensions,
          metrics
        };
      }

      const response = await fetch(buildApiUrl(`/graphs/${graphId}/semantic`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
        body: JSON.stringify(payload),
        credentials: 'include'
      });

      if (!response.ok) throw new Error("Lưu thất bại");
      
      toast({ title: "Thành công", description: "Đã lưu Semantic Layer" });
      
      if (source === 'visual') {
        setJsonText(JSON.stringify(payload, null, 2));
      } else {
        const parsed = JSON.parse(jsonText);
        setDimensions(parsed.dimensions || []);
        setMetrics(parsed.metrics || []);
      }
    } catch (err: any) {
      toast({ title: "Lỗi lưu Schema", description: err.message, variant: "destructive" });
    } finally {
      setIsSaving(false);
    }
  };

  const openEditModal = (type: 'dimension' | 'metric', index: number | null = null) => {
    if (index !== null) {
      const item = type === 'dimension' ? dimensions[index] : metrics[index];
      setEditItem({ type, index, data: { ...item } });
    } else {
      setEditItem({ type, index: null, data: { name: '', type: '', description: '', expr: '' } });
    }
  };

  const saveEditItem = () => {
    if (!editItem) return;
    const { type, index, data } = editItem;
    if (!data.name || !data.description) {
      toast({ title: "Thiếu thông tin", description: "Vui lòng nhập tên và mô tả", variant: "destructive" });
      return;
    }

    if (type === 'dimension') {
      const newArr = [...dimensions];
      if (index !== null) newArr[index] = data; else newArr.push(data);
      setDimensions(newArr);
    } else {
      const newArr = [...metrics];
      if (index !== null) newArr[index] = data; else newArr.push(data);
      setMetrics(newArr);
    }
    setEditItem(null);
  };

  const deleteItem = (type: 'dimension' | 'metric', index: number) => {
    if (type === 'dimension') {
      setDimensions(dimensions.filter((_, i) => i !== index));
    } else {
      setMetrics(metrics.filter((_, i) => i !== index));
    }
  };

  const renderTable = (type: 'dimension' | 'metric', items: SemanticItem[]) => (
    <div className="border border-gray-100 dark:border-gray-800 rounded-2xl overflow-hidden bg-white dark:bg-[#09090b] shadow-sm">
      <div className="flex justify-between items-center p-4 border-b border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50">
        <h3 className="font-bold text-gray-700 dark:text-gray-300 capitalize">{type}s ({items.length})</h3>
        <Button size="sm" onClick={() => openEditModal(type)} className="h-8 rounded-full shadow-sm">
          <Plus className="w-4 h-4 mr-1" /> Add {type}
        </Button>
      </div>
      {items.length === 0 ? (
        <div className="p-12 text-center text-gray-400">
          <p>Chưa có {type} nào được định nghĩa.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-gray-500 uppercase bg-gray-50/50 dark:bg-gray-900/50 border-b border-gray-100 dark:border-gray-800">
              <tr>
                <th className="px-6 py-3 font-semibold">Tên (Name)</th>
                <th className="px-6 py-3 font-semibold">Loại (Type)</th>
                <th className="px-6 py-3 font-semibold">Mô tả (Description)</th>
                <th className="px-6 py-3 font-semibold">Biểu thức (Expr)</th>
                <th className="px-6 py-3 text-right font-semibold">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {items.map((item, idx) => (
                <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors">
                  <td className="px-6 py-3 font-semibold text-gray-900 dark:text-gray-100">{item.name}</td>
                  <td className="px-6 py-3">
                    <span className="px-2 py-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-md text-xs">{item.type || 'N/A'}</span>
                  </td>
                  <td className="px-6 py-3 text-gray-500 max-w-xs truncate" title={item.description}>{item.description}</td>
                  <td className="px-6 py-3 text-gray-500 font-mono text-xs">{item.expr || item.sql || '-'}</td>
                  <td className="px-6 py-3 text-right">
                    <Button variant="ghost" size="icon" onClick={() => openEditModal(type, idx)} className="h-8 w-8 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-500/10 mr-1">
                      <Edit2 className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => deleteItem(type, idx)} className="h-8 w-8 text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10">
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
  );

  return (
    <div className="flex flex-col h-full bg-[#fafafa] dark:bg-[#09090b] font-sans relative">
      {/* Header */}
      <div className="flex items-center justify-between px-8 py-5 bg-white dark:bg-black/50 border-b border-gray-100 dark:border-gray-800 shrink-0 shadow-sm z-10">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => navigate(-1)} className="rounded-full shadow-sm hover:bg-gray-100 dark:hover:bg-gray-800">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg">
              <Network className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">Semantic Layer</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400 font-medium">Configuring knowledge layer for Data Source</p>
            </div>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center flex-1">
          <Loader2 className="w-10 h-10 animate-spin text-primary mb-4" />
          <p className="text-gray-500 font-medium">Đang tải cấu trúc ngữ nghĩa...</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-6xl mx-auto space-y-6">
            <Tabs defaultValue="visual" className="w-full">
              <div className="flex justify-between items-center mb-6">
                <TabsList className="bg-gray-100/80 dark:bg-gray-800/80 p-1 rounded-xl h-11">
                  <TabsTrigger value="visual" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm px-6">
                    <LayoutList className="w-4 h-4 mr-2" />
                    Visual Builder
                  </TabsTrigger>
                  <TabsTrigger value="json" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm px-6">
                    <Code className="w-4 h-4 mr-2" />
                    Raw JSON
                  </TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="visual" className="space-y-6 outline-none mt-0">
                {renderTable('dimension', dimensions)}
                {renderTable('metric', metrics)}
                
                <div className="flex justify-end pt-4">
                  <Button onClick={() => handleSave('visual')} disabled={isSaving} className="rounded-full px-8 shadow-md h-11 bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/90 hover:to-indigo-600/90 text-white font-bold">
                    {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                    Save Visual Changes
                  </Button>
                </div>
              </TabsContent>

              <TabsContent value="json" className="outline-none mt-0">
                <div className="border border-gray-100 dark:border-gray-800 rounded-2xl overflow-hidden shadow-sm bg-white dark:bg-gray-900">
                  <div className="p-4 bg-gray-50 dark:bg-gray-900/50 border-b border-gray-100 dark:border-gray-800 flex justify-between items-center">
                    <span className="font-semibold text-sm text-gray-700 dark:text-gray-300">Edit raw semantic configuration</span>
                  </div>
                  <textarea
                    value={jsonText}
                    onChange={(e) => setJsonText(e.target.value)}
                    className="w-full h-[500px] p-6 font-mono text-sm bg-transparent border-0 focus:ring-0 text-gray-800 dark:text-gray-200 resize-none outline-none"
                    spellCheck={false}
                  />
                </div>
                <div className="flex justify-end pt-6">
                  <Button onClick={() => handleSave('json')} disabled={isSaving} className="rounded-full px-8 shadow-md h-11 bg-gradient-to-r from-primary to-indigo-600 text-white font-bold">
                    {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                    Save JSON
                  </Button>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      <Dialog open={!!editItem} onOpenChange={(open) => !open && setEditItem(null)}>
        <DialogContent className="sm:max-w-[500px] rounded-[24px]">
          <DialogHeader>
            <DialogTitle className="capitalize font-bold text-xl">{editItem?.index !== null ? 'Edit' : 'Add'} {editItem?.type}</DialogTitle>
          </DialogHeader>
          {editItem && (
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label>Tên (Name)</Label>
                <Input value={editItem.data.name} onChange={e => setEditItem({...editItem, data: {...editItem.data, name: e.target.value}})} className="rounded-xl" />
              </div>
              <div className="grid gap-2">
                <Label>Loại (Type)</Label>
                <Input value={editItem.data.type} onChange={e => setEditItem({...editItem, data: {...editItem.data, type: e.target.value}})} placeholder="e.g. string, number, date" className="rounded-xl" />
              </div>
              <div className="grid gap-2">
                <Label>Biểu thức (Expression / SQL)</Label>
                <Input value={editItem.data.expr || editItem.data.sql || ''} onChange={e => setEditItem({...editItem, data: {...editItem.data, expr: e.target.value}})} placeholder="e.g. count(id)" className="rounded-xl font-mono text-sm" />
              </div>
              <div className="grid gap-2">
                <Label>Mô tả (Description)</Label>
                <Input value={editItem.data.description} onChange={e => setEditItem({...editItem, data: {...editItem.data, description: e.target.value}})} placeholder="Giải thích ý nghĩa..." className="rounded-xl" />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditItem(null)} className="rounded-full px-6">Huỷ</Button>
            <Button onClick={saveEditItem} className="rounded-full px-6">Lưu</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default V4Semantic;
