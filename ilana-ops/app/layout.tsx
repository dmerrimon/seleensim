'use client';

import { useEffect, useState } from 'react';
import { MsalProvider } from '@azure/msal-react';
import { PublicClientApplication, EventType } from '@azure/msal-browser';
import { msalConfig } from '@/lib/msal-config';
import './globals.css';

// Initialize MSAL instance
const msalInstance = new PublicClientApplication(msalConfig);

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    const initializeMsal = async () => {
      try {
        await msalInstance.initialize();

        // Handle redirect promise
        await msalInstance.handleRedirectPromise();

        // Set active account if there's one
        const accounts = msalInstance.getAllAccounts();
        if (accounts.length > 0) {
          msalInstance.setActiveAccount(accounts[0]);
        }

        // Listen for login events
        msalInstance.addEventCallback((event) => {
          if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
            const payload = event.payload as { account?: { username: string } };
            if (payload.account) {
              msalInstance.setActiveAccount(payload.account as any);
            }
          }
        });

        setIsInitialized(true);
      } catch (error) {
        console.error('MSAL initialization error:', error);
        // Still set initialized to true so the app can render
        // Dev mode will work even if MSAL fails
        setIsInitialized(true);
      }
    };

    initializeMsal();
  }, []);

  return (
    <html lang="en">
      <body>
        {isInitialized ? (
          <MsalProvider instance={msalInstance}>
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
