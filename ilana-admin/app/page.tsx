'use client';

import { useEffect } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { useRouter } from 'next/navigation';
import { loginRequest } from '@/lib/msal-config';

export default function Home() {
  const { instance } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, router]);

  const handleLogin = () => {
    instance.loginRedirect(loginRequest);
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
        <p className="login-subtitle">Admin Portal</p>

        <p className="text-muted mb-4">
          Sign in with your Microsoft account to manage seats and users.
        </p>

        <button className="btn btn-primary" onClick={handleLogin} style={{ width: '100%' }}>
          Sign in with Microsoft
        </button>

        <p className="text-small text-muted mt-4">
          Only organization admins can access this portal.
        </p>
      </div>
    </div>
  );
}
