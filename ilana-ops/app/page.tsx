'use client';

import { useEffect } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { useRouter } from 'next/navigation';
import { loginRequest } from '@/lib/msal-config';
import { isDevMode } from '@/lib/mock-data';

export default function Home() {
  const { instance } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const router = useRouter();
  const devMode = isDevMode();

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, router]);

  const handleLogin = () => {
    instance.loginRedirect(loginRequest);
  };

  const handleDevLogin = () => {
    // Store dev mode flag in sessionStorage
    sessionStorage.setItem('ilana_dev_mode', 'true');
    router.push('/dashboard');
  };

  if (isAuthenticated) {
    return (
      <div className="login-container">
        <div className="login-card">
          <div className="spinner" style={{ margin: '0 auto' }}></div>
          <p className="mt-4 text-muted">Redirecting to dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-logo">ILANA</div>
        <p className="login-subtitle">Ops Portal</p>

        <p className="text-muted mb-4">
          Internal operations dashboard for managing tenants and users.
        </p>

        <button className="btn btn-primary" onClick={handleLogin} style={{ width: '100%' }}>
          Sign in with Microsoft
        </button>

        {devMode && (
          <>
            <div style={{ margin: '16px 0', textAlign: 'center', color: '#666' }}>
              — or —
            </div>
            <button
              className="btn"
              onClick={handleDevLogin}
              style={{
                width: '100%',
                background: '#ff9800',
                color: 'white',
                border: 'none',
                padding: '12px',
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              Dev Login (Mock Data)
            </button>
            <p className="text-small text-muted mt-2" style={{ color: '#ff9800' }}>
              Dev mode enabled - using mock data
            </p>
          </>
        )}

        <p className="text-small text-muted mt-4">
          Only Ilana super admins can access this portal.
        </p>
      </div>
    </div>
  );
}
