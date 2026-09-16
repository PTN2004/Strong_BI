import { getCsrfToken } from '@/lib/csrf';

const originalFetch = window.fetch.bind(window);

export const apiFetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const headers = new Headers(init?.headers);
  
  // Lấy workspace id từ localStorage nếu có
  const activeWorkspaceId = localStorage.getItem('activeWorkspaceId');
  if (activeWorkspaceId && !headers.has('X-Workspace-Id')) {
    headers.set('X-Workspace-Id', activeWorkspaceId);
  }
  
  // Auto-attach CSRF token for state-changing requests if present in cookies
  const csrfToken = getCsrfToken();
  if (csrfToken && !headers.has('X-CSRF-Token')) {
    headers.set('X-CSRF-Token', csrfToken);
  }
  
  const modifiedInit: RequestInit = {
    credentials: 'include',
    ...init,
    headers,
  };
  
  return originalFetch(input, modifiedInit);
};
