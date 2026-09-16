import { buildApiUrl } from '../config/api';
import { Dashboard } from '../types/api';
import { apiFetch } from '../utils/apiFetch';

export const dashboardService = {
  getDashboards: async (): Promise<Dashboard[]> => {
    const response = await apiFetch(buildApiUrl('/dashboards'), {
      headers: {
        'Content-Type': 'application/json',
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch dashboards');
    }
    
    const data = await response.json();
    return data.dashboards || [];
  },
  
  getDashboard: async (id: string): Promise<Dashboard> => {
    const response = await apiFetch(buildApiUrl(`/dashboards/${id}`), {
      headers: {
        'Content-Type': 'application/json',
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch dashboard');
    }
    
    return response.json();
  },
  
  createDashboard: async (name: string, description?: string): Promise<{ id: string; name?: string }> => {
    const response = await apiFetch(buildApiUrl('/dashboards'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name, description, widgets: [] }),
    });
    
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || 'Failed to create dashboard');
    }
    
    return response.json();
  },
  
  addWidget: async (dashboardId: string, widget: any): Promise<any> => {
    const response = await apiFetch(buildApiUrl(`/dashboards/${dashboardId}/widgets`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(widget),
    });
    
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || 'Failed to add widget');
    }
    
    return response.json();
  },
  
  updateWidget: async (dashboardId: string, widgetId: string, data: any): Promise<any> => {
    const response = await apiFetch(buildApiUrl(`/dashboards/${dashboardId}/widgets/${widgetId}`), {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || 'Failed to update widget');
    }
    
    return response.json();
  },

  deleteWidget: async (dashboardId: string, widgetId: string): Promise<void> => {
    const response = await apiFetch(buildApiUrl(`/dashboards/${dashboardId}/widgets/${widgetId}`), {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      }
    });
    
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || 'Failed to delete widget');
    }
  },
  
  deleteDashboard: async (id: string): Promise<void> => {
    const response = await apiFetch(buildApiUrl(`/dashboards/${id}`), {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      }
    });
    
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || 'Failed to delete dashboard');
    }
  }
};
