'use client';

import { useEffect, useState, useCallback } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { useRouter } from 'next/navigation';
import { apiRequest } from '@/lib/msal-config';
import { fetchDashboard, revokeUserSeat, restoreUserSeat, DashboardData } from '@/lib/api';
import { mockDashboardData, isDevMode } from '@/lib/mock-data';

export default function Dashboard() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const router = useRouter();

  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [isDevSession, setIsDevSession] = useState(false);

  // Check for dev mode session
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const devSession = sessionStorage.getItem('ilana_dev_mode') === 'true';
      setIsDevSession(devSession);
    }
  }, []);

  // Get access token
  const getToken = useCallback(async () => {
    if (accounts.length === 0) return null;

    try {
      const response = await instance.acquireTokenSilent({
        ...apiRequest,
        account: accounts[0],
      });
      return response.accessToken;
    } catch (e) {
      // Fallback to interactive
      const response = await instance.acquireTokenPopup(apiRequest);
      return response.accessToken;
    }
  }, [instance, accounts]);

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
    } catch (e: any) {
      setError(e.message || 'Failed to load dashboard');
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

  // Handle seat revocation
  const handleRevoke = async (userId: string, userName: string) => {
    if (!confirm(`Revoke seat for ${userName}? They will lose access until restored.`)) {
      return;
    }

    try {
      setActionLoading(userId);
      const token = await getToken();
      if (!token) return;

      await revokeUserSeat(userId, { token });
      await loadData(); // Refresh
    } catch (e: any) {
      alert(`Failed to revoke: ${e.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Handle seat restoration
  const handleRestore = async (userId: string) => {
    try {
      setActionLoading(userId);
      const token = await getToken();
      if (!token) return;

      await restoreUserSeat(userId, { token });
      await loadData(); // Refresh
    } catch (e: any) {
      alert(`Failed to restore: ${e.message}`);
    } finally {
      setActionLoading(null);
    }
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
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return `${diffDays} days ago`;
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
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container" style={{ paddingTop: 40 }}>
        <div className="alert alert-error">
          {error}
          <button className="btn btn-outline btn-small" onClick={loadData} style={{ marginLeft: 16 }}>
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
      {/* Header */}
      <header className="header">
        <div className="container header-content">
          <div className="logo">ILANA <span>Admin</span></div>
          <button className="btn btn-outline" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="container" style={{ paddingTop: 32, paddingBottom: 64 }}>
        {/* Trial Status Banner */}
        {data.trial && data.trial.is_trial && (
          <div className={`trial-banner trial-banner-${data.trial.status}`}>
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
                >
                  Subscribe Now &rarr;
                </a>
              </>
            )}
            {data.trial.status === 'expired' && (
              <>
                <span className="trial-badge trial-badge-expired">EXPIRED</span>
                <span className="trial-text">
                  Trial ended &mdash; {data.trial.grace_days_remaining ?? 0} day{(data.trial.grace_days_remaining ?? 0) !== 1 ? 's' : ''} to subscribe
                </span>
                <a
                  href="https://appsource.microsoft.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="trial-link trial-link-urgent"
                >
                  Subscribe to Continue &rarr;
                </a>
              </>
            )}
            {data.trial.status === 'blocked' && (
              <>
                <span className="trial-badge trial-badge-blocked">BLOCKED</span>
                <span className="trial-text">
                  Trial expired &mdash; Subscribe to restore access
                </span>
                <a
                  href="https://appsource.microsoft.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="trial-link trial-link-urgent"
                >
                  Subscribe Now &rarr;
                </a>
              </>
            )}
          </div>
        )}

        {/* Active Subscription Banner */}
        {data.trial && !data.trial.is_trial && (
          <div className="trial-banner trial-banner-active">
            <span className="trial-badge trial-badge-active">SUBSCRIBED</span>
            <span className="trial-text">Active subscription</span>
          </div>
        )}

        {/* Seat Usage */}
        <div className="card seat-usage">
          <div className="seat-usage-header">
            <span className="seat-usage-label">
              {data.subscription.seats_used} / {data.subscription.seats_total} seats used
            </span>
            <span className="text-muted">
              {data.subscription.seats_available} available
            </span>
          </div>
          <div className="seat-usage-bar">
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
        </div>

        {/* Users Table */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Users ({data.stats.total_users})</h2>
            <button className="btn btn-outline btn-small" onClick={loadData}>
              Refresh
            </button>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Last Active</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.users.map((user) => (
                  <tr key={user.id}>
                    <td>
                      {user.display_name || 'Unknown'}
                      {user.is_admin && (
                        <span className="badge badge-gray" style={{ marginLeft: 8 }}>Admin</span>
                      )}
                    </td>
                    <td>{user.email || '-'}</td>
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
                        <span className="text-muted text-small">-</span>
                      ) : user.has_seat ? (
                        <button
                          className="btn btn-danger btn-small"
                          onClick={() => handleRevoke(user.id, user.display_name || user.email || 'this user')}
                          disabled={actionLoading === user.id}
                        >
                          {actionLoading === user.id ? '...' : 'Revoke'}
                        </button>
                      ) : (
                        <button
                          className="btn btn-outline btn-small"
                          onClick={() => handleRestore(user.id)}
                          disabled={actionLoading === user.id || data.subscription.seats_available === 0}
                        >
                          {actionLoading === user.id ? '...' : 'Restore'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </>
  );
}
