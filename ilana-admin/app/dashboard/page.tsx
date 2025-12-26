'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { useRouter } from 'next/navigation';
import { apiRequest } from '@/lib/msal-config';
import { fetchDashboard, revokeUserSeat, restoreUserSeat, transferAdmin, DashboardData } from '@/lib/api';
import { mockDashboardData, isDevMode } from '@/lib/mock-data';
import Header from '@/components/Header';

// Toast notification types
type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

// Confirmation modal state
interface ConfirmModal {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  confirmText?: string;
  confirmVariant?: 'danger' | 'primary';
}

export default function Dashboard() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const router = useRouter();

  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [isDevSession, setIsDevSession] = useState(false);

  // Toast notifications state
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);

  // Confirmation modal state
  const [confirmModal, setConfirmModal] = useState<ConfirmModal>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
  });

  // Show toast notification
  const showToast = useCallback((type: ToastType, message: string) => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, type, message }]);
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  }, []);

  // Dismiss toast
  const dismissToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Show confirmation modal
  const showConfirm = useCallback((
    title: string,
    message: string,
    onConfirm: () => void,
    options?: { confirmText?: string; confirmVariant?: 'danger' | 'primary' }
  ) => {
    setConfirmModal({
      isOpen: true,
      title,
      message,
      onConfirm,
      confirmText: options?.confirmText || 'Confirm',
      confirmVariant: options?.confirmVariant || 'primary',
    });
  }, []);

  // Close confirmation modal
  const closeConfirm = useCallback(() => {
    setConfirmModal(prev => ({ ...prev, isOpen: false }));
  }, []);

  // Check for dev mode session
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const devSession = sessionStorage.getItem('ilana_dev_mode') === 'true';
      setIsDevSession(devSession);
    }
  }, []);

  // Get access token with proper error handling
  const getToken = useCallback(async (): Promise<string | null> => {
    if (accounts.length === 0) return null;

    try {
      const response = await instance.acquireTokenSilent({
        ...apiRequest,
        account: accounts[0],
      });
      return response.accessToken;
    } catch (silentError) {
      // Fallback to interactive with error handling
      try {
        const response = await instance.acquireTokenPopup(apiRequest);
        return response.accessToken;
      } catch (popupError) {
        const errorMessage = popupError instanceof Error
          ? popupError.message
          : 'Failed to acquire authentication token';
        showToast('error', errorMessage);
        return null;
      }
    }
  }, [instance, accounts, showToast]);

  // Load dashboard data
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Use mock data in dev mode
      if (isDevSession || isDevMode()) {
        // Simulate network delay
        await new Promise(resolve => setTimeout(resolve, 500));
        setData(mockDashboardData);
        setLoading(false);
        return;
      }

      const token = await getToken();
      if (!token) {
        router.push('/');
        return;
      }

      const dashboard = await fetchDashboard({ token });
      setData(dashboard);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load dashboard';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [getToken, router, isDevSession]);

  useEffect(() => {
    // Allow access in dev mode without authentication
    if (isDevSession || isDevMode()) {
      loadData();
      return;
    }

    if (!isAuthenticated) {
      router.push('/');
      return;
    }
    loadData();
  }, [isAuthenticated, router, loadData, isDevSession]);

  // Handle seat revocation with confirmation modal
  const handleRevoke = async (userId: string, userName: string) => {
    showConfirm(
      'Revoke Seat Access',
      `Are you sure you want to revoke seat access for ${userName}? They will lose access until restored.`,
      async () => {
        closeConfirm();
        try {
          setActionLoading(userId);
          const token = await getToken();
          if (!token) {
            showToast('error', 'Authentication required');
            return;
          }

          await revokeUserSeat(userId, { token });
          showToast('success', `Seat revoked for ${userName}`);
          await loadData(); // Refresh
        } catch (err: unknown) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to revoke seat';
          showToast('error', errorMessage);
        } finally {
          setActionLoading(null);
        }
      },
      { confirmText: 'Revoke Access', confirmVariant: 'danger' }
    );
  };

  // Handle seat restoration
  const handleRestore = async (userId: string, userName: string) => {
    try {
      setActionLoading(userId);
      const token = await getToken();
      if (!token) {
        showToast('error', 'Authentication required');
        return;
      }

      await restoreUserSeat(userId, { token });
      showToast('success', `Seat restored for ${userName}`);
      await loadData(); // Refresh
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to restore seat';
      showToast('error', errorMessage);
    } finally {
      setActionLoading(null);
    }
  };

  // Handle admin transfer with confirmation
  const handleMakeAdmin = async (userId: string, userName: string) => {
    showConfirm(
      'Transfer Admin Role',
      `Are you sure you want to transfer admin access to ${userName}? You will lose your admin privileges and be redirected to the home page.`,
      async () => {
        closeConfirm();
        try {
          setActionLoading(userId);
          const token = await getToken();
          if (!token) {
            showToast('error', 'Authentication required');
            return;
          }

          await transferAdmin(userId, { token });
          showToast('success', `Admin role transferred to ${userName}. Redirecting...`);
          // Redirect to home since current user is no longer admin
          setTimeout(() => router.push('/'), 2000);
        } catch (err: unknown) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to transfer admin';
          showToast('error', errorMessage);
        } finally {
          setActionLoading(null);
        }
      },
      { confirmText: 'Transfer Admin', confirmVariant: 'danger' }
    );
  };

  // Handle logout
  const handleLogout = () => {
    instance.logoutRedirect();
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

  // Check if user is inactive (30+ days)
  const isInactive = (dateStr: string | null) => {
    if (!dateStr) return true;
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
    return diffDays >= 30;
  };

  if (loading) {
    return (
      <div
        className="loading-container"
        role="status"
        aria-label="Loading dashboard"
      >
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
          <button
            className="btn btn-outline btn-small"
            onClick={loadData}
            aria-label="Retry loading dashboard"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const usagePercent = (data.subscription.seats_used / data.subscription.seats_total) * 100;

  return (
    <>
      {/* Toast Notifications */}
      <div className="toast-container" role="region" aria-label="Notifications">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`toast toast-${toast.type}`}
            role="alert"
            aria-live="polite"
          >
            <span className="toast-message">{toast.message}</span>
            <button
              className="toast-dismiss"
              onClick={() => dismissToast(toast.id)}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        ))}
      </div>

      {/* Confirmation Modal */}
      {confirmModal.isOpen && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
        >
          <div className="modal">
            <h2 id="modal-title" className="modal-title">{confirmModal.title}</h2>
            <p className="modal-message">{confirmModal.message}</p>
            <div className="modal-actions">
              <button
                className="btn btn-outline"
                onClick={closeConfirm}
              >
                Cancel
              </button>
              <button
                className={`btn ${confirmModal.confirmVariant === 'danger' ? 'btn-danger' : 'btn-primary'}`}
                onClick={confirmModal.onConfirm}
              >
                {confirmModal.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <Header onLogout={handleLogout} />

      {/* Main Content */}
      <main className="container main-content" role="main">
        {/* Trial Status Banner */}
        {data.trial && data.trial.is_trial && (
          <div
            className={`trial-banner trial-banner-${data.trial.status}`}
            role="status"
            aria-label={`Trial status: ${data.trial.status}`}
          >
            {data.trial.status === 'trial' && (
              <>
                <span className="trial-badge">TRIAL</span>
                <span className="trial-text">
                  {data.trial.days_remaining} day{data.trial.days_remaining !== 1 ? 's' : ''} remaining
                </span>
                <a
                  href="https://appsource.microsoft.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="trial-link"
                  aria-label="Subscribe now on Microsoft AppSource"
                >
                  Subscribe Now →
                </a>
              </>
            )}
            {data.trial.status === 'expired' && (
              <>
                <span className="trial-badge trial-badge-expired">EXPIRED</span>
                <span className="trial-text">
                  Trial ended — {data.trial.grace_days_remaining ?? 0} day{(data.trial.grace_days_remaining ?? 0) !== 1 ? 's' : ''} to subscribe
                </span>
                <a
                  href="https://appsource.microsoft.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="trial-link trial-link-urgent"
                  aria-label="Subscribe to continue using Ilana"
                >
                  Subscribe to Continue →
                </a>
              </>
            )}
            {data.trial.status === 'blocked' && (
              <>
                <span className="trial-badge trial-badge-blocked">BLOCKED</span>
                <span className="trial-text">
                  Trial expired — Subscribe to restore access
                </span>
                <a
                  href="https://appsource.microsoft.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="trial-link trial-link-urgent"
                  aria-label="Subscribe now to restore access"
                >
                  Subscribe Now →
                </a>
              </>
            )}
          </div>
        )}

        {/* Active Subscription Banner */}
        {data.trial && !data.trial.is_trial && (
          <div className="trial-banner trial-banner-active" role="status">
            <span className="trial-badge trial-badge-active">SUBSCRIBED</span>
            <span className="trial-text">Active subscription</span>
          </div>
        )}

        {/* Seat Usage */}
        <section className="card seat-usage" aria-labelledby="seat-usage-title">
          <h2 id="seat-usage-title" className="sr-only">Seat Usage</h2>
          <div className="seat-usage-header">
            <span className="seat-usage-label">
              {data.subscription.seats_used} / {data.subscription.seats_total} seats used
            </span>
            <span className="text-muted">
              {data.subscription.seats_available} available
            </span>
          </div>
          <div
            className="seat-usage-bar"
            role="progressbar"
            aria-valuenow={Math.round(usagePercent)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${Math.round(usagePercent)}% of seats used`}
          >
            <div
              className={`seat-usage-fill ${usagePercent >= 90 ? 'danger' : usagePercent >= 70 ? 'warning' : ''}`}
              style={{ width: `${usagePercent}%` }}
            />
          </div>
          {data.stats.inactive_users > 0 && (
            <p className="text-small text-muted mt-4">
              {data.stats.inactive_users} user{data.stats.inactive_users > 1 ? 's' : ''} inactive for 30+ days
            </p>
          )}
        </section>

        {/* Users Table */}
        <section className="card" aria-labelledby="users-title">
          <div className="card-header">
            <h2 id="users-title" className="card-title">Users ({data.stats.total_users})</h2>
            <button
              className="btn btn-outline btn-small"
              onClick={loadData}
              aria-label="Refresh user list"
            >
              Refresh
            </button>
          </div>

          <div className="table-container">
            <table aria-describedby="users-title">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Email</th>
                  <th scope="col">Last Active</th>
                  <th scope="col">Status</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.users.map((user) => (
                  <tr key={user.id}>
                    <td>
                      {user.display_name || 'Unknown'}
                      {user.is_admin && (
                        <span className="badge badge-gray admin-badge">Admin</span>
                      )}
                    </td>
                    <td>{user.email || '—'}</td>
                    <td>
                      <span className={isInactive(user.last_active_at) && user.has_seat ? 'text-muted' : ''}>
                        {formatRelativeTime(user.last_active_at)}
                        {isInactive(user.last_active_at) && user.has_seat && ' (inactive)'}
                      </span>
                    </td>
                    <td>
                      {user.has_seat ? (
                        <span className="badge badge-success">Active Seat</span>
                      ) : (
                        <span className="badge badge-gray">No Seat</span>
                      )}
                    </td>
                    <td>
                      {user.is_admin ? (
                        <span className="text-muted text-small">—</span>
                      ) : user.has_seat ? (
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button
                            className="btn btn-outline btn-small"
                            onClick={() => handleMakeAdmin(user.id, user.display_name || user.email || 'this user')}
                            disabled={actionLoading === user.id}
                            aria-label={`Make ${user.display_name || user.email} admin`}
                            aria-busy={actionLoading === user.id}
                          >
                            {actionLoading === user.id ? (
                              <span className="btn-loading">
                                <span className="spinner-small" aria-hidden="true"></span>
                                <span className="sr-only">Transferring...</span>
                              </span>
                            ) : 'Make Admin'}
                          </button>
                          <button
                            className="btn btn-danger btn-small"
                            onClick={() => handleRevoke(user.id, user.display_name || user.email || 'this user')}
                            disabled={actionLoading === user.id}
                            aria-label={`Revoke seat access for ${user.display_name || user.email}`}
                            aria-busy={actionLoading === user.id}
                          >
                            {actionLoading === user.id ? (
                              <span className="btn-loading">
                                <span className="spinner-small" aria-hidden="true"></span>
                                <span className="sr-only">Revoking...</span>
                              </span>
                            ) : 'Revoke'}
                          </button>
                        </div>
                      ) : (
                        <button
                          className="btn btn-outline btn-small"
                          onClick={() => handleRestore(user.id, user.display_name || user.email || 'this user')}
                          disabled={actionLoading === user.id || data.subscription.seats_available === 0}
                          aria-label={`Restore seat access for ${user.display_name || user.email}`}
                          aria-busy={actionLoading === user.id}
                          title={data.subscription.seats_available === 0 ? 'No seats available' : undefined}
                        >
                          {actionLoading === user.id ? (
                            <span className="btn-loading">
                              <span className="spinner-small" aria-hidden="true"></span>
                              <span className="sr-only">Restoring...</span>
                            </span>
                          ) : 'Restore'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </>
  );
}
