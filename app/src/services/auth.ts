import { API_CONFIG, buildApiUrl } from '@/config/api';
import { csrfHeaders } from '@/lib/csrf';
import type { AuthStatus, User } from '@/types/api';

/**
 * Authentication Service
 * Handles OAuth authentication with Google and GitHub
 */

export class AuthService {
  /**
   * Check current authentication status
   */
  static async checkAuthStatus(): Promise<AuthStatus> {
    try {
      const response = await fetch(buildApiUrl(API_CONFIG.ENDPOINTS.AUTH_STATUS), {
        credentials: 'include', // Important: include cookies for session
      });

      // 403 = Not authenticated (normal state - user can still use the app)
      if (response.status === 403) {
        console.log('Not authenticated - you can still use QueryWeaver, sign in to save databases');
        return { authenticated: false };
      }

      if (!response.ok) {
        return { authenticated: false };
      }

      const data = await response.json();
      return data;
    } catch (error) {
      // Backend not available - return unauthenticated for demo mode
      console.log('Backend not available for auth - using demo mode');
      return { authenticated: false };
    }
  }

  /**
   * Check if backend is available
   */
  static async checkBackendAvailable(): Promise<boolean> {
    try {
      await fetch(buildApiUrl('/health').replace('/health', ''), {
        method: 'HEAD',
        mode: 'no-cors'
      });
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Initiate Google OAuth login
   * Redirects to Google OAuth flow
   */
  static async loginWithGoogle(): Promise<void> {
    try {
      // First check if backend is available
      const url = buildApiUrl(API_CONFIG.ENDPOINTS.LOGIN_GOOGLE);
      console.log('Redirecting to Google OAuth:', url);
      
      // Just redirect - let the backend handle the OAuth flow
      window.location.href = url;
    } catch (error) {
      console.error('Failed to initiate Google login:', error);
      throw new Error('Failed to connect to authentication service. Please ensure the backend is running and OAuth is configured.');
    }
  }

  /**
   * Initiate GitHub OAuth login
   * Redirects to GitHub OAuth flow
   */
  static async loginWithGithub(): Promise<void> {
    try {
      const url = buildApiUrl(API_CONFIG.ENDPOINTS.LOGIN_GITHUB);
      console.log('Redirecting to GitHub OAuth:', url);
      
      // Just redirect - let the backend handle the OAuth flow
      window.location.href = url;
    } catch (error) {
      console.error('Failed to initiate GitHub login:', error);
      throw new Error('Failed to connect to authentication service. Please ensure the backend is running and OAuth is configured.');
    }
  }

  /**
   * Local Login with Email/Password
   */
  static async loginWithEmail(email: string, password: string): Promise<void> {
    const response = await fetch(buildApiUrl('/login/email'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...csrfHeaders(),
      },
      body: JSON.stringify({ email, password }),
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMsg = 'Login failed';
      try {
        const data = await response.json();
        errorMsg = data.detail || data.error || errorMsg;
      } catch (e) {}
      throw new Error(errorMsg);
    }
  }

  /**
   * Local Registration with Email/Password
   */
  static async registerWithEmail(firstName: string, lastName: string, email: string, password: string): Promise<void> {
    const response = await fetch(buildApiUrl('/signup/email'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...csrfHeaders(),
      },
      body: JSON.stringify({ firstName, lastName, email, password }),
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMsg = 'Registration failed';
      try {
        const data = await response.json();
        errorMsg = data.detail || data.error || errorMsg;
      } catch (e) {}
      throw new Error(errorMsg);
    }
  }

  /**
   * Logout current user
   */
  static async logout(): Promise<void> {
    try {
      await fetch(buildApiUrl(API_CONFIG.ENDPOINTS.LOGOUT), {
        method: 'POST',
        credentials: 'include',
        headers: {
          ...csrfHeaders(),
        },
      });
    } catch (error) {
      console.error('Failed to logout:', error);
      throw error;
    }
  }

  /**
   * Get current user information
   */
  static async getCurrentUser(): Promise<User | null> {
    try {
      const response = await fetch(buildApiUrl(API_CONFIG.ENDPOINTS.USER), {
        credentials: 'include',
      });

      if (!response.ok) {
        return null;
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Failed to get current user:', error);
      return null;
    }
  }

  /**
   * List all users (Admin only)
   */
  static async getUsers(): Promise<any[]> {
    const response = await fetch(buildApiUrl('/users'), {
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error('Failed to fetch user list');
    }

    return response.json();
  }

  /**
   * Update user role and active status (Admin only)
   */
  static async updateUser(userId: string, role?: string, isActive?: boolean): Promise<void> {
    const response = await fetch(buildApiUrl(`/users/${userId}`), {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...csrfHeaders(),
      },
      body: JSON.stringify({ role, isActive }),
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error('Failed to update user profile');
    }
  }

  /**
   * Create a new user (Admin only)
   */
  static async createUser(data: {
    firstName: string;
    lastName: string;
    email: string;
    password: string;
    role: string;
  }): Promise<any> {
    const response = await fetch(buildApiUrl('/users'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...csrfHeaders(),
      },
      body: JSON.stringify(data),
      credentials: 'include',
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create user');
    }

    return response.json();
  }

  /**
   * Delete a user (Admin only)
   */
  static async deleteUser(userId: string): Promise<void> {
    const response = await fetch(buildApiUrl(`/users/${userId}`), {
      method: 'DELETE',
      headers: {
        ...csrfHeaders(),
      },
      credentials: 'include',
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to delete user');
    }
  }
}

