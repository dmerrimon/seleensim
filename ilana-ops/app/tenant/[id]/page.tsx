'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { apiRequest } from '@/lib/msal-config';
import {
  validateSession,
  fetchTenantDetail,
  extendTrial,
  TenantDetail,
  TenantUser,
} from '@/lib/api';
import { isDevMode, mockTenantDetail } from '@/lib/mock-data';
import Header from '@/components/Header';

// Toast notification types
type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

export default function TenantDetailPage() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const router = useRouter();
  const params = useParams();
  const tenantId = params.id as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDevSession, setIsDevSession] = useState(false);
  const [tenant, setTenant] = useState<TenantDetail | null>(null);

  // Extend trial modal
  const [extendModal, setExtendModal] = useState(false);
  const [extendDays, setExtendDays] = useState(14);
  const [extendLoading, setExtendLoading] = useState(false);

  // Toast notifications
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);

  const showToast = useCallback((type: ToastType, message: string) => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Check for dev mode session
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const devSession = sessionStorage.getItem('ilana_dev_mode') === 'true';
      setIsDevSession(devSession);
    }
  }, []);

  // Get access token
  const getToken = useCallback(async (): Promise<string | null> => {
    if (accounts.length === 0) return null;
    try {
      const response = await instance.acquireTokenSilent({
        ...apiRequest,
        account: accounts[0],
      });
      return response.accessToken;
    } catch {
      try {
        const response = await instance.acquireTokenPopup(apiRequest);
        return response.accessToken;
      } catch {
        return null;
      }
    }
  }, [instance, accounts]);

  // Load data
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Use mock data in dev mode
      if (isDevSession || isDevMode()) {
        await new Promise(resolve => setTimeout(resolve, 500));
        setTenant(mockTenantDetail);
        setLoading(false);
        return;
      }

      const token = await getToken();
      if (!token) {
        router.push('/');
        return;
      }

      // Validate user is super admin
      const sessionData = await validateSession({ token });
      if (!sessionData.user?.is_super_admin) {
        router.push('/');
        return;
      }

      // Fetch tenant detail
      const tenantData = await fetchTenantDetail(tenantId, { token });
      setTenant(tenantData);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load tenant';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [getToken, router, tenantId, isDevSession]);

  useEffect(() => {
    if (isDevSession || isDevMode() || isAuthenticated) {
      loadData();
    } else if (!isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, router, loadData, isDevSession]);

  // Handle extend trial
  const handleExtendTrial = async () => {
    try {
      setExtendLoading(true);

      if (isDevSession || isDevMode()) {
        await new Promise(resolve => setTimeout(resolve, 500));
        showToast('success', `Extended trial by ${extendDays} days`);
        setExtendModal(false);
        return;
      }

      const token = await getToken();
      if (!token) return;

      await extendTrial(tenantId, extendDays, { token });
      showToast('success', `Extended trial by ${extendDays} days`);
      setExtendModal(false);
      loadData();
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to extend trial');
    } finally {
      setExtendLoading(false);
    }
  };

  // Handle logout
  const handleLogout = () => {
    if (isDevSession) {
      sessionStorage.removeItem('ilana_dev_mode');
      router.push('/');
    } else {
      instance.logoutRedirect();
    }
  };

  // Format date
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  // Format relative time
  const formatRelativeTime = (dateStr: string | null) => {
    if (!dateStr) return 'Never';

    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) {
      const weeks = Math.floor(diffDays / 7);
      return `${weeks} week${weeks !== 1 ? 's' : ''} ago`;
    }
    const months = Math.floor(diffDays / 30);
    return `${months} month${months !== 1 ? 's' : ''} ago`;
  };

  // Status badge helper
  const getStatusBadge = (status: string) => {
    if (status === 'active') {
      return <span className="badge badge-success">Active</span>;
    }
    if (status === 'trial') {
      return <span className="badge badge-warning">Trial</span>;
    }
    if (status === 'expired') {
      return <span className="badge badge-error">Expired</span>;
    }
    if (status === 'cancelled') {
      return <span className="badge badge-gray">Cancelled</span>;
    }
    return <span className="badge badge-gray">Unknown</span>;
  };

  if (loading) {
    return (
      <div className="loading-container" role="status">
        <div className="spinner" aria-hidden="true"></div>
        <span className="sr-only">Loading...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container error-container">
        <div className="alert alert-error" role="alert">
          <span>{error}</span>
          <button className="btn btn-outline btn-small" onClick={loadData}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!tenant) {
    return null;
  }

  return (
    <>
      {/* Toast Notifications */}
      <div className="toast-container" role="region" aria-label="Notifications">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast-${toast.type}`} role="alert">
            <span className="toast-message">{toast.message}</span>
            <button className="toast-dismiss" onClick={() => dismissToast(toast.id)}>
              x
            </button>
          </div>
        ))}
      </div>

      {/* Extend Trial Modal */}
      {extendModal && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal">
            <h2 className="modal-title">Extend Trial</h2>
            <p className="modal-message">
              Extend trial for <strong>{tenant.name}</strong>
            </p>
            <div style={{ marginBottom: '16px' }}>
              <label htmlFor="extend-days" style={{ display: 'block', marginBottom: '8px' }}>
                Days to add:
              </label>
              <input
                id="extend-days"
                type="number"
                min="1"
                max="90"
                value={extendDays}
                onChange={(e) => setExtendDays(Number(e.target.value))}
                className="input"
                style={{ width: '100px' }}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setExtendModal(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleExtendTrial}
                disabled={extendLoading}
              >
                {extendLoading ? 'Extending...' : 'Extend Trial'}
              </button>
            </div>
          </div>
        </div>
      )}

      <Header onLogout={handleLogout} />

      <main className="container main-content" role="main">
        {/* Breadcrumb */}
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link href="/dashboard" className="breadcrumb-link">
            Dashboard
          </Link>
          <span className="breadcrumb-separator">/</span>
          <span className="breadcrumb-current">{tenant.name || 'Tenant'}</span>
        </nav>

        <div className="page-header">
          <h1 className="page-title">{tenant.name || 'Unnamed Tenant'}</h1>
          {(tenant.subscription?.status === 'trial' || tenant.subscription?.status === 'expired') && (
            <button className="btn btn-primary" onClick={() => setExtendModal(true)}>
              Extend Trial
            </button>
          )}
        </div>

        {/* Tenant Info Card */}
        <section className="card">
          <h2 className="card-title">Tenant Information</h2>
          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">Azure Tenant ID</span>
              <span className="info-value code">{tenant.azure_tenant_id}</span>
            </div>
            <div className="info-item">
              <span className="info-label">Created</span>
              <span className="info-value">{formatDate(tenant.created_at)}</span>
            </div>
            <div className="info-item">
              <span className="info-label">Subscription Status</span>
              <span className="info-value">
                {tenant.subscription ? getStatusBadge(tenant.subscription.status) : <span className="badge badge-gray">No Subscription</span>}
              </span>
            </div>
            <div className="info-item">
              <span className="info-label">Plan Type</span>
              <span className="info-value">{tenant.subscription?.plan_type || 'None'}</span>
            </div>
            <div className="info-item">
              <span className="info-label">Seats</span>
              <span className="info-value">
                {tenant.subscription
                  ? `${tenant.subscription.seats_used} / ${tenant.subscription.seats_total}`
                  : 'N/A'}
              </span>
            </div>
            {tenant.subscription?.trial_ends_at && (
              <div className="info-item">
                <span className="info-label">Trial Ends</span>
                <span className="info-value">{formatDate(tenant.subscription.trial_ends_at)}</span>
              </div>
            )}
          </div>
        </section>

        {/* Users Section */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">Users ({tenant.users.length})</h2>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last Active</th>
                </tr>
              </thead>
              <tbody>
                {tenant.users.map((user: TenantUser) => (
                  <tr key={user.id}>
                    <td>{user.display_name || '—'}</td>
                    <td>{user.email || '—'}</td>
                    <td>
                      {user.is_admin ? (
                        <span className="badge badge-blue">Admin</span>
                      ) : (
                        <span className="text-muted">User</span>
                      )}
                    </td>
                    <td>
                      {user.has_seat ? (
                        <span className="badge badge-success">Active Seat</span>
                      ) : (
                        <span className="badge badge-gray">No Seat</span>
                      )}
                    </td>
                    <td>{formatRelativeTime(user.last_active_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <style jsx>{`
        .breadcrumb {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 16px;
          font-size: 14px;
        }

        .breadcrumb-link {
          color: var(--primary-color);
          text-decoration: none;
        }

        .breadcrumb-link:hover {
          text-decoration: underline;
        }

        .breadcrumb-separator {
          color: var(--gray-400);
        }

        .breadcrumb-current {
          color: var(--gray-600);
        }

        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }

        .page-title {
          font-size: 24px;
          font-weight: 600;
          margin: 0;
        }

        .info-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 20px;
        }

        .info-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .info-label {
          font-size: 13px;
          color: var(--gray-500);
          font-weight: 500;
        }

        .info-value {
          font-size: 15px;
          color: var(--gray-900);
        }

        .info-value.code {
          font-family: monospace;
          font-size: 13px;
          background: var(--gray-100);
          padding: 4px 8px;
          border-radius: 4px;
          word-break: break-all;
        }

        .input {
          padding: 8px 12px;
          border: 1px solid var(--gray-200);
          border-radius: 6px;
          font-size: 14px;
        }

        .input:focus {
          outline: none;
          border-color: var(--primary-color);
        }

        .badge-blue {
          background: #dbeafe;
          color: #2563eb;
        }

        .badge-error {
          background: #fee2e2;
          color: #dc2626;
        }
      `}</style>
    </>
  );
}
