import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SchemaMetadataEditor } from '@/components/schema/SchemaMetadataEditor';

const V4SchemaMetadata = () => {
  const { graphId } = useParams<{ graphId: string }>();
  const navigate = useNavigate();

  if (!graphId) {
    return <div className="p-8 text-center text-muted-foreground">No graph ID provided.</div>;
  }

  return (
    <div className="flex flex-col h-full w-full bg-[#f8f9fc] dark:bg-[#09090b]">
      {/* Header */}
      <div className="flex items-center gap-4 p-6 bg-white dark:bg-[#09090b] border-b border-border shadow-sm shrink-0">
        <Button 
          variant="outline" 
          size="icon" 
          onClick={() => navigate('/databases')}
          className="rounded-xl h-10 w-10 border-border/70 shadow-sm"
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">
            Edit Schema Metadata
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Database: {graphId}
          </p>
        </div>
      </div>

      {/* Editor Content */}
      <div className="flex-1 overflow-hidden p-6">
        <div className="bg-white dark:bg-black rounded-2xl shadow-sm border border-border h-full overflow-hidden">
          <SchemaMetadataEditor graphId={graphId} />
        </div>
      </div>
    </div>
  );
};

export default V4SchemaMetadata;
