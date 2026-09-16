import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Workspace } from '../types/api';
import { useAuth } from './AuthContext';
import { apiFetch } from '@/utils/apiFetch';
import { buildApiUrl } from '@/config/api';

interface WorkspaceContextType {
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  setActiveWorkspace: (workspace: Workspace) => void;
  isLoading: boolean;
  refreshWorkspaces: () => Promise<void>;
  createWorkspace: (name: string, industry?: string, businessGoals?: string, kpiFocus?: string) => Promise<Workspace>;
  deleteWorkspace: (id: string) => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export const WorkspaceProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { user, refreshAuth } = useAuth();
  const workspaces = user?.workspaces || [];
  
  const [activeWorkspace, setActiveWorkspaceState] = useState<Workspace | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  
  useEffect(() => {
    if (workspaces.length > 0) {
      // Check if we have a saved preference
      const savedId = localStorage.getItem('activeWorkspaceId');
      const saved = workspaces.find(w => w.id === savedId);
      
      if (saved) {
        setActiveWorkspaceState(saved);
      } else {
        // Default to first workspace
        setActiveWorkspaceState(workspaces[0]);
        localStorage.setItem('activeWorkspaceId', workspaces[0].id);
      }
    } else {
      setActiveWorkspaceState(null);
    }
  }, [user]);

  const setActiveWorkspace = (workspace: Workspace) => {
    setActiveWorkspaceState(workspace);
    localStorage.setItem('activeWorkspaceId', workspace.id);
  };

  const createWorkspace = async (name: string, industry?: string, businessGoals?: string, kpiFocus?: string): Promise<Workspace> => {
    setIsLoading(true);
    try {
      const response = await apiFetch(buildApiUrl('/workspaces'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          industry,
          business_goals: businessGoals,
          kpi_focus: kpiFocus,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.error || 'Failed to create workspace');
      }

      const data = await response.json();
      await refreshAuth();
      
      const newWs = data.workspace;
      if (newWs) {
        setActiveWorkspace(newWs);
      }
      return newWs;
    } finally {
      setIsLoading(false);
    }
  };

  const deleteWorkspace = async (id: string): Promise<void> => {
    setIsLoading(true);
    try {
      const response = await apiFetch(buildApiUrl(`/workspaces/${id}`), {
        method: 'DELETE',
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.error || 'Failed to delete workspace');
      }

      await refreshAuth();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        activeWorkspace,
        setActiveWorkspace,
        isLoading,
        refreshWorkspaces: refreshAuth,
        createWorkspace,
        deleteWorkspace,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = () => {
  const context = useContext(WorkspaceContext);
  if (context === undefined) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider');
  }
  return context;
};
