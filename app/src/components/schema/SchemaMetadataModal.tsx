import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { SchemaMetadataEditor } from './SchemaMetadataEditor';

interface SchemaMetadataModalProps {
  isOpen: boolean;
  onClose: () => void;
  graphId: string;
}

export const SchemaMetadataModal = ({ isOpen, onClose, graphId }: SchemaMetadataModalProps) => {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-7xl w-[95vw] h-[90vh] bg-background border-border shadow-2xl rounded-2xl flex flex-col overflow-hidden p-0 gap-0">
        <DialogHeader className="p-4 border-b shrink-0 bg-muted/30">
          <DialogTitle className="text-xl font-bold">Edit Schema Metadata</DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-hidden p-4">
          <SchemaMetadataEditor graphId={graphId} />
        </div>
      </DialogContent>
    </Dialog>
  );
};
