import { useState, useEffect, useCallback } from 'react';

// Declare OfficeRuntime global for SSO (provided by office-runtime.js)
declare const OfficeRuntime: {
  auth: {
    getAccessToken(options?: {
      allowSignInPrompt?: boolean;
      allowConsentPrompt?: boolean;
      forMSGraphAccess?: boolean;
    }): Promise<string>;
  };
};

interface UseAuthReturn {
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  getToken: () => Promise<string | null>;
}

/**
 * Hook for Office Add-in authentication using Azure AD SSO
 * Uses Office.auth.getAccessToken() to get the user's Azure AD token
 */
export function useAuth(): UseAuthReturn {
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const getToken = useCallback(async (): Promise<string | null> => {
    // Check if Office.js is available
    if (typeof Office === 'undefined' || typeof OfficeRuntime === 'undefined') {
      console.log('Office.js not available - running in standalone mode');
      return null;
    }

    try {
      // Get SSO token from Office
      const accessToken = await OfficeRuntime.auth.getAccessToken({
        allowSignInPrompt: true,
        allowConsentPrompt: true,
      });

      setToken(accessToken);
      setError(null);
      return accessToken;
    } catch (err: any) {
      console.error('Auth error:', err);

      // Handle specific Office auth errors
      if (err.code === 13001) {
        // User not signed in
        setError('Please sign in to continue');
      } else if (err.code === 13002) {
        // Consent required
        setError('Please grant permission to access your account');
      } else if (err.code === 13003) {
        // Resource not allowed
        setError('Authentication configuration error');
      } else {
        setError('Authentication failed');
      }

      setToken(null);
      return null;
    }
  }, []);

  // Try to get token on mount
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      await getToken();
      setIsLoading(false);
    };

    // Wait for Office to be ready
    if (typeof Office !== 'undefined') {
      Office.onReady(() => {
        initAuth();
      });
    } else {
      setIsLoading(false);
    }
  }, [getToken]);

  return {
    token,
    isAuthenticated: !!token,
    isLoading,
    error,
    getToken,
  };
}
