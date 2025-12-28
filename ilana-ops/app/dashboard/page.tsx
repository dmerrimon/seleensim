'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiRequest } from '@/lib/msal-config';
import {
  validateSession,
  fetchAllTenants,
  fetchSuperAdminStats,
  searchUsers,
  extendTrial,
  fetchSuperAdmins,
  grantSuperAdmin,
  revokeSuperAdmin,
  TenantSummary,
  SuperAdminStats,
  UserSearchResult,
  SuperAdminInfo,
} from '@/lib/api';
import { isDevMode, mockStats, mockTenants, mockSuperAdmins } from '@/lib/mock-data';
import Header from '@/components/Header';

// Toast notification types
type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

export default function OpsDashboard() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDevSession, setIsDevSession] = useState(false);

  // Data state
  const [stats, setStats] = useState<SuperAdminStats | null>(null);
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [superAdmins, setSuperAdmins] = useState<SuperAdminInfo[]>([]);

  // Search state
  const [searchEmail, setSearchEmail] = useState('');
  const [searchResults, setSearchResults] = useState<UserSearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // Extend trial modal
  const [extendModal, setExtendModal] = useState<{ tenantId: string; tenantName: string } | null>(null);
  const [extendDays, setExtendDays] = useState(14);
  const [extendLoading, setExtendLoading] = useState(false);

  // Grant super admin modal
  const [grantModal, setGrantModal] = useState(false);
  const [grantEmail, setGrantEmail] = useState('');
  const [grantLoading, setGrantLoading] = useState(false);

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
        setStats(mockStats);
        setTenants(mockTenants);
        setSuperAdmins(mockSuperAdmins);
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
        // Not a super admin - redirect to login with error
        router.push('/');
        return;
      }

      // Fetch super admin data
      const [statsData, tenantsData, superAdminsData] = await Promise.all([
        fetchSuperAdminStats({ token }),
        fetchAllTenants({ token }),
        fetchSuperAdmins({ token }),
      ]);

      setStats(statsData);
      setTenants(tenantsData);
      setSuperAdmins(superAdminsData);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load data';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [getToken, router, isDevSession]);

  useEffect(() => {
    if (isDevSession || isDevMode() || isAuthenticated) {
      loadData();
    } else if (!isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, router, loadData, isDevSession]);

  // Handle user search
  const handleSearch = async () => {
    if (!searchEmail.trim()) return;

    try {
      setSearching(true);

      if (isDevSession || isDevMode()) {
        await new Promise(resolve => setTimeout(resolve, 300));
        setSearchResults([
          {
            id: '1',
            email: searchEmail,
            display_name: 'Search Result User',
            tenant_id: '1',
            tenant_name: 'Pfizer Inc',
            is_admin: false,
            is_super_admin: false,
            has_seat: true,
            last_active_at: new Date().toISOString(),
          },
        ]);
        return;
      }

      const token = await getToken();
      if (!token) return;

      const results = await searchUsers(searchEmail, { token });
      setSearchResults(results);
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  // Handle extend trial
  const handleExtendTrial = async () => {
    if (!extendModal) return;

    try {
      setExtendLoading(true);

      if (isDevSession || isDevMode()) {
        await new Promise(resolve => setTimeout(resolve, 500));
        showToast('success', `Extended trial for ${extendModal.tenantName} by ${extendDays} days`);
        setExtendModal(null);
        return;
      }

      const token = await getToken();
      if (!token) return;

      await extendTrial(extendModal.tenantId, extendDays, { token });
      showToast('success', `Extended trial for ${extendModal.tenantName} by ${extendDays} days`);
      setExtendModal(null);
      loadData();
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to extend trial');
    } finally {
      setExtendLoading(false);
    }
  };

  // Handle grant super admin
  const handleGrantSuperAdmin = async () => {
    if (!grantEmail.trim()) return;

    try {
      setGrantLoading(true);

      if (isDevSession || isDevMode()) {
        await new Promise(resolve => setTimeout(resolve, 500));
        showToast('success', `Granted super admin to ${grantEmail}`);
        setGrantModal(false);
        setGrantEmail('');
        return;
      }

      const token = await getToken();
      if (!token) return;

      await grantSuperAdmin(grantEmail, { token });
      showToast('success', `Granted super admin to ${grantEmail}`);
      setGrantModal(false);
      setGrantEmail('');
      loadData();
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to grant super admin');
    } finally {
      setGrantLoading(false);
    }
  };

  // Handle revoke super admin
  const handleRevokeSuperAdmin = async (userId: string, email: string) => {
    if (!confirm(`Are you sure you want to revoke super admin access from ${email}?`)) return;

    try {
      if (isDevSession || isDevMode()) {
        await new Promise(resolve => setTimeout(resolve, 500));
        showToast('success', `Revoked super admin from ${email}`);
        return;
      }

      const token = await getToken();
      if (!token) return;

      await revokeSuperAdmin(userId, { token });
      showToast('success', `Revoked super admin from ${email}`);
      loadData();
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to revoke super admin');
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

  // Status badge helper
  const getStatusBadge = (status: string | null, trialDays: number | null) => {
    if (status === 'active') {
      return <span className="badge badge-success">Active</span>;
    }
    if (status === 'trial') {
      return <span className="badge badge-warning">Trial ({trialDays}d)</span>;
    }
    if (status === 'expired') {
      return <span className="badge badge-error">Expired</span>;
    }
    if (status === 'cancelled') {
      return <span className="badge badge-gray">Cancelled</span>;
    }
    return <span className="badge badge-gray">Unknown</span>;
  };

  // Format date
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
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
              Extend trial for <strong>{extendModal.tenantName}</strong>
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
              <button className="btn btn-outline" onClick={() => setExtendModal(null)}>
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

      {/* Grant Super Admin Modal */}
      {grantModal && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal">
            <h2 className="modal-title">Grant Super Admin</h2>
            <p className="modal-message">
              Enter the email address of the user to grant super admin access.
            </p>
            <div style={{ marginBottom: '16px' }}>
              <label htmlFor="grant-email" style={{ display: 'block', marginBottom: '8px' }}>
                Email address:
              </label>
              <input
                id="grant-email"
                type="email"
                value={grantEmail}
                onChange={(e) => setGrantEmail(e.target.value)}
                className="input"
                placeholder="user@company.com"
                style={{ width: '100%' }}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setGrantModal(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleGrantSuperAdmin}
                disabled={grantLoading || !grantEmail.trim()}
              >
                {grantLoading ? 'Granting...' : 'Grant Super Admin'}
              </button>
            </div>
          </div>
        </div>
      )}

      <Header onLogout={handleLogout} />

      <main className="container main-content" role="main">
        <h1 className="page-title">Operations Dashboard</h1>

        {/* Stats Cards */}
        {stats && (
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{stats.total_tenants}</div>
              <div className="stat-label">Total Tenants</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.total_users}</div>
              <div className="stat-label">Total Users</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.active_subscriptions}</div>
              <div className="stat-label">Active Subscriptions</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.trials_active}</div>
              <div className="stat-label">Active Trials</div>
            </div>
          </div>
        )}

        {/* User Search */}
        <section className="card">
          <h2 className="card-title">Search Users</h2>
          <div className="search-row">
            <input
              type="text"
              placeholder="Search by email..."
              value={searchEmail}
              onChange={(e) => setSearchEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="input"
              style={{ flex: 1 }}
            />
            <button
              className="btn btn-primary"
              onClick={handleSearch}
              disabled={searching || !searchEmail.trim()}
            >
              {searching ? 'Searching...' : 'Search'}
            </button>
          </div>

          {searchResults.length > 0 && (
            <div className="table-container" style={{ marginTop: '16px' }}>
              <table>
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Name</th>
                    <th>Tenant</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {searchResults.map((user) => (
                    <tr key={user.id}>
                      <td>{user.email || '—'}</td>
                      <td>{user.display_name || '—'}</td>
                      <td>
                        <Link href={`/tenant/${user.tenant_id}`} className="link">
                          {user.tenant_name || 'Unknown'}
                        </Link>
                      </td>
                      <td>
                        {user.is_super_admin && <span className="badge badge-purple">Super</span>}
                        {user.is_admin && <span className="badge badge-blue">Admin</span>}
                        {user.has_seat ? (
                          <span className="badge badge-success">Active</span>
                        ) : (
                          <span className="badge badge-gray">No Seat</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* All Tenants */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">All Tenants</h2>
            <button className="btn btn-outline btn-small" onClick={loadData}>
              Refresh
            </button>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Users</th>
                  <th>Seats</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {tenants.map((tenant) => (
                  <tr key={tenant.id}>
                    <td>
                      <Link href={`/tenant/${tenant.id}`} className="link">
                        {tenant.name || 'Unnamed Tenant'}
                      </Link>
                    </td>
                    <td>{tenant.user_count}</td>
                    <td>
                      {tenant.seats_used}/{tenant.seats_total}
                    </td>
                    <td>
                      {getStatusBadge(tenant.subscription_status, tenant.trial_days_remaining)}
                    </td>
                    <td>{formatDate(tenant.created_at)}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <Link href={`/tenant/${tenant.id}`} className="btn btn-outline btn-small">
                          View
                        </Link>
                        {(tenant.subscription_status === 'trial' || tenant.subscription_status === 'expired') && (
                          <button
                            className="btn btn-outline btn-small"
                            onClick={() => setExtendModal({ tenantId: tenant.id, tenantName: tenant.name || 'Unnamed' })}
                          >
                            Extend
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Super Admins Section */}
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">Super Admins</h2>
            <button className="btn btn-primary btn-small" onClick={() => setGrantModal(true)}>
              Add Super Admin
            </button>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {superAdmins.map((admin) => (
                  <tr key={admin.id}>
                    <td>{admin.display_name || '—'}</td>
                    <td>{admin.email || '—'}</td>
                    <td>
                      {superAdmins.length > 1 && (
                        <button
                          className="btn btn-danger btn-small"
                          onClick={() => handleRevokeSuperAdmin(admin.id, admin.email || 'this user')}
                        >
                          Revoke
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

      <style jsx>{`
        .page-title {
          margin-bottom: 24px;
          font-size: 24px;
          font-weight: 600;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 16px;
          margin-bottom: 24px;
        }

        .stat-card {
          background: var(--gray-50);
          border-radius: 8px;
          padding: 20px;
          text-align: center;
        }

        .stat-value {
          font-size: 32px;
          font-weight: 600;
          color: var(--gray-900);
        }

        .stat-label {
          font-size: 14px;
          color: var(--gray-500);
          margin-top: 4px;
        }

        .search-row {
          display: flex;
          gap: 12px;
          align-items: center;
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

        .link {
          color: var(--primary-color);
          text-decoration: none;
        }

        .link:hover {
          text-decoration: underline;
        }

        .badge-purple {
          background: #f3e8ff;
          color: #7c3aed;
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
