'use client';

import { useEffect, useState, useRef } from 'react';
import { MsalProvider } from '@azure/msal-react';
import { PublicClientApplication, EventType } from '@azure/msal-browser';
import { msalConfig } from '@/lib/msal-config';
import './globals.css';

// Initialize MSAL instance outside component to avoid re-creation
let msalInstance: PublicClientApplication | null = null;

function getMsalInstance() {
  if (!msalInstance) {
    msalInstance = new PublicClientApplication(msalConfig);
  }
  return msalInstance;
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isInitialized, setIsInitialized] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);
  const initAttempted = useRef(false);

  useEffect(() => {
    // Prevent double initialization in React Strict Mode
    if (initAttempted.current) return;
    initAttempted.current = true;

    const initializeMsal = async () => {
      // Add a timeout to prevent infinite loading
      const timeoutId = setTimeout(() => {
        console.warn('MSAL initialization timed out, proceeding without auth');
        setIsInitialized(true);
      }, 5000);

      try {
        const instance = getMsalInstance();
        await instance.initialize();

        // Handle redirect promise
        await instance.handleRedirectPromise();

        // Set active account if there's one
        const accounts = instance.getAllAccounts();
        if (accounts.length > 0) {
          instance.setActiveAccount(accounts[0]);
        }

        // Listen for login events
        instance.addEventCallback((event) => {
          if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
            const payload = event.payload as { account?: { username: string } };
            if (payload.account) {
              instance.setActiveAccount(payload.account as any);
            }
          }
        });

        clearTimeout(timeoutId);
        setIsInitialized(true);
      } catch (error) {
        clearTimeout(timeoutId);
        console.error('MSAL initialization error:', error);
        setInitError(error instanceof Error ? error.message : 'Unknown error');
        // Still set initialized to true so the app can render
        // Dev mode will work even if MSAL fails
        setIsInitialized(true);
      }
    };

    initializeMsal();
  }, []);

  // Show error state if there was an init error but still render
  if (initError) {
    console.warn('MSAL init error (app will still render):', initError);
  }

  return (
    <html lang="en">
      <body>
        {isInitialized ? (
          <MsalProvider instance={getMsalInstance()}>
            {children}
          </MsalProvider>
        ) : (
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh',
            fontFamily: 'system-ui, sans-serif'
          }}>
            Loading...
          </div>
        )}
      </body>
    </html>
  );
}
