import React, { useEffect, useState } from 'react';
import { Loader2, Save, Database, Table as TableIcon, LayoutList } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { DatabaseService } from '@/services/database';

interface SchemaMetadataEditorProps {
  graphId: string;
}

type ColumnMetadata = {
  name: string;
  type: string;
  description: string;
  key_type: string;
};

type TableMetadata = {
  table_name: string;
  description: string;
  columns: ColumnMetadata[];
};

export const SchemaMetadataEditor = ({ graphId }: SchemaMetadataEditorProps) => {
  const [metadata, setMetadata] = useState<TableMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  
  // State for unsaved changes
  const [tableDesc, setTableDesc] = useState('');
  const [colDescs, setColDescs] = useState<Record<string, string>>({});
  
  const [savingTable, setSavingTable] = useState(false);
  const [savingCol, setSavingCol] = useState<string | null>(null);

  const { toast } = useToast();

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await DatabaseService.getSchemaMetadata(graphId);
      setMetadata(data);
      if (data.length > 0 && !selectedTable) {
        handleSelectTable(data[0]);
      } else if (selectedTable) {
        const table = data.find((t: TableMetadata) => t.table_name === selectedTable);
        if (table) {
            handleSelectTable(table);
        }
      }
    } catch (error: any) {
      toast({ title: 'Failed to load metadata', description: error.message, variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [graphId]);

  const handleSelectTable = (table: TableMetadata) => {
    setSelectedTable(table.table_name);
    setTableDesc(table.description || '');
    const cDescs: Record<string, string> = {};
    table.columns.forEach(c => {
      cDescs[c.name] = c.description || '';
    });
    setColDescs(cDescs);
  };

  const handleSaveTable = async () => {
    if (!selectedTable) return;
    try {
      setSavingTable(true);
      await DatabaseService.updateSchemaMetadata(graphId, {
        type: 'table',
        table_name: selectedTable,
        description: tableDesc
      });
      toast({ title: 'Success', description: 'Table description updated successfully' });
      setMetadata(prev => prev.map(t => t.table_name === selectedTable ? { ...t, description: tableDesc } : t));
    } catch (error: any) {
      toast({ title: 'Failed to save', description: error.message, variant: 'destructive' });
    } finally {
      setSavingTable(false);
    }
  };

  const handleSaveColumn = async (columnName: string) => {
    if (!selectedTable) return;
    try {
      setSavingCol(columnName);
      await DatabaseService.updateSchemaMetadata(graphId, {
        type: 'column',
        table_name: selectedTable,
        column_name: columnName,
        description: colDescs[columnName] || ''
      });
      toast({ title: 'Success', description: `Column ${columnName} description updated` });
      
      setMetadata(prev => prev.map(t => {
        if (t.table_name === selectedTable) {
            return {
                ...t,
                columns: t.columns.map(c => c.name === columnName ? { ...c, description: colDescs[columnName] || '' } : c)
            };
        }
        return t;
      }));
    } catch (error: any) {
      toast({ title: 'Failed to save', description: error.message, variant: 'destructive' });
    } finally {
      setSavingCol(null);
    }
  };

  if (loading && metadata.length === 0) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  const currentTable = metadata.find(t => t.table_name === selectedTable);

  return (
    <div className="flex h-full bg-white dark:bg-black overflow-hidden">
      {/* Sidebar */}
      <div className="w-[280px] border-r border-gray-100 dark:border-gray-800 bg-[#fbfbfb] dark:bg-[#0a0a0c] flex flex-col shrink-0">
        <div className="p-5 border-b border-gray-100 dark:border-gray-800 flex items-center gap-2">
          <Database className="w-4 h-4 text-blue-600" />
          <span className="font-bold text-gray-900 dark:text-gray-100">Tables ({metadata.length})</span>
        </div>
        <div className="overflow-y-auto flex-1 p-3 space-y-1">
          {metadata.map(table => (
            <button
              key={table.table_name}
              onClick={() => handleSelectTable(table)}
              className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors flex items-center gap-2 ${
                selectedTable === table.table_name 
                  ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 font-medium' 
                  : 'hover:bg-muted text-muted-foreground'
              }`}
            >
              <TableIcon className="w-4 h-4 opacity-70" />
              <span className="truncate">{table.table_name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-black">
        {currentTable ? (
          <div className="flex-1 overflow-y-auto p-8 space-y-10">
            {/* Table Metadata */}
            <div className="space-y-5">
              <div className="flex items-center gap-3 pb-3 border-b border-gray-100 dark:border-gray-800">
                <TableIcon className="w-6 h-6 text-emerald-500" />
                <h2 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">{currentTable.table_name}</h2>
              </div>
              
              <div className="space-y-3">
                <label className="text-sm font-bold text-gray-700 dark:text-gray-300">Table Description</label>
                <div className="flex gap-4 items-start max-w-4xl">
                  <Textarea 
                    value={tableDesc}
                    onChange={(e) => setTableDesc(e.target.value)}
                    placeholder="Describe what this table is used for in the business..."
                    className="min-h-[100px] resize-y bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-800 focus:bg-white text-base"
                  />
                  <Button 
                    onClick={handleSaveTable} 
                    disabled={savingTable || tableDesc === currentTable.description}
                    className="shrink-0 h-11 px-6 bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm"
                  >
                    {savingTable ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                    Save
                  </Button>
                </div>
                <p className="text-sm text-gray-500 italic mt-2">
                  Note: Updating the description will re-calculate its semantic vector for better AI accuracy.
                </p>
              </div>
            </div>

            {/* Columns Metadata */}
            <div className="space-y-5">
              <div className="flex items-center gap-2 pb-3 border-b border-gray-100 dark:border-gray-800">
                <LayoutList className="w-5 h-5 text-blue-500" />
                <h3 className="text-xl font-bold tracking-tight text-gray-900 dark:text-white">Columns</h3>
              </div>
              
              <div className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden bg-white dark:bg-black shadow-sm">
                <table className="w-full text-sm text-left">
                  <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wider font-semibold">
                    <tr>
                      <th className="px-6 py-4 w-1/4">Name / Type</th>
                      <th className="px-6 py-4 w-3/4">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {currentTable.columns.map((col) => (
                      <tr key={col.name} className="hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors">
                        <td className="px-6 py-5 align-top">
                          <div className="font-bold text-gray-900 dark:text-white text-base">{col.name}</div>
                          <div className="text-sm text-gray-500 font-mono mt-1.5 bg-gray-100 dark:bg-gray-800 inline-block px-2 py-0.5 rounded">{col.type}</div>
                          {col.key_type && col.key_type !== 'NONE' && (
                            <div className="text-[11px] uppercase font-bold text-amber-600 bg-amber-50 dark:bg-amber-500/10 inline-block px-2 py-0.5 rounded ml-2 mt-1.5">{col.key_type}</div>
                          )}
                        </td>
                        <td className="px-6 py-5">
                          <div className="flex gap-3">
                            <Textarea 
                              value={colDescs[col.name] ?? ''}
                              onChange={(e) => setColDescs(prev => ({ ...prev, [col.name]: e.target.value }))}
                              placeholder="Add column description..."
                              className="min-h-[80px] text-sm resize-y bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-800 focus:bg-white"
                            />
                            <Button 
                              variant="outline" 
                              onClick={() => handleSaveColumn(col.name)}
                              disabled={savingCol === col.name || colDescs[col.name] === col.description}
                              className="shrink-0 mt-1 h-10 w-10 p-0 rounded-xl"
                            >
                              {savingCol === col.name ? <Loader2 className="w-4 h-4 animate-spin text-blue-600" /> : <Save className="w-4 h-4 text-blue-600" />}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {currentTable.columns.length === 0 && (
                      <tr>
                        <td colSpan={2} className="px-4 py-8 text-center text-muted-foreground italic">
                          No columns found for this table.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            Select a table to edit its metadata
          </div>
        )}
      </div>
    </div>
  );
};
