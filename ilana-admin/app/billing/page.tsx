'use client';

import { useEffect, useState, useCallback } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { useRouter } from 'next/navigation';
import { apiRequest } from '@/lib/msal-config';
import { fetchBillingStatus, BillingStatus } from '@/lib/api';
import { isDevMode, mockBillingStatus } from '@/lib/mock-data';
import Header from '@/components/Header';

export default function BillingPage() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const router = useRouter();

  const [billingData, setBillingData] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDevSession, setIsDevSession] = useState(false);

  // Check for dev mode session
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const devSession = sessionStorage.getItem('ilana_dev_mode') === 'true';
      setIsDevSession(devSession);
    }
  }, []);

  // Auth check
  useEffect(() => {
    if (!isDevSession && !isDevMode() && !isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, router, isDevSession]);

  // Get access token
  const getToken = useCallback(async (): Promise<string | null> => {
    if (accounts.length === 0) return null;
    try {
      const response = await instance.acquireTokenSilent({
        ...apiRequest,
        account: accounts[0],
      });
      return response.accessToken;
    } catch (e) {
      console.error('Failed to acquire token:', e);
      return null;
    }
  }, [instance, accounts]);

  // Fetch billing data
  useEffect(() => {
    const loadBillingData = async () => {
      // Use mock data in dev mode
      if (isDevSession || isDevMode()) {
        setBillingData(mockBillingStatus);
        setLoading(false);
        return;
      }

      try {
        const token = await getToken();
        if (!token) {
          setError('Unable to authenticate');
          setLoading(false);
          return;
        }

        // Fetch billing data
        const data = await fetchBillingStatus({ token });
        setBillingData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load billing data');
      } finally {
        setLoading(false);
      }
    };

    if (isAuthenticated || isDevSession || isDevMode()) {
      loadBillingData();
    }
  }, [isAuthenticated, isDevSession, getToken]);

  // Handle logout
  const handleLogout = () => {
    if (isDevSession) {
      sessionStorage.removeItem('ilana_dev_mode');
      router.push('/');
    } else {
      instance.logoutRedirect();
    }
  };

  // Format date for display
  const formatDate = (dateString: string | null): string => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  // Get status badge class
  const getStatusBadgeClass = (status: string): string => {
    switch (status) {
      case 'active':
        return 'status-badge status-badge-active';
      case 'trial':
        return 'status-badge status-badge-trial';
      case 'past_due':
        return 'status-badge status-badge-warning';
      case 'expired':
      case 'cancelled':
        return 'status-badge status-badge-error';
      default:
        return 'status-badge';
    }
  };

  // Get status label
  const getStatusLabel = (status: string): string => {
    switch (status) {
      case 'active':
        return 'Active';
      case 'trial':
        return 'Trial';
      case 'past_due':
        return 'Past Due';
      case 'expired':
        return 'Expired';
      case 'cancelled':
        return 'Cancelled';
      default:
        return status;
    }
  };

  return (
    <>
      <Header onLogout={handleLogout} />

      <main className="container main-content" role="main">
        <h1 className="page-title">Billing</h1>

        {loading && (
          <div className="card">
            <p className="text-muted">Loading billing information...</p>
          </div>
        )}

        {error && (
          <div className="card card-error">
            <p>{error}</p>
          </div>
        )}

        {billingData && !loading && (
          <>
            {/* Status Banner */}
            {billingData.message && (
              <div className={`billing-banner billing-banner-${billingData.status}`}>
                <span>{billingData.message}</span>
              </div>
            )}

            {/* Subscription Status Card */}
            <div className="card">
              <h2 className="card-title">Subscription Status</h2>
              <div className="billing-grid">
                <div className="billing-item">
                  <span className="billing-label">Status</span>
                  <span className={getStatusBadgeClass(billingData.status)}>
                    {getStatusLabel(billingData.status)}
                  </span>
                </div>
                <div className="billing-item">
                  <span className="billing-label">Plan</span>
                  <span className="billing-value">
                    {billingData.is_trial ? 'Free Trial' : 'Ilana Pro'}
                  </span>
                </div>
                <div className="billing-item">
                  <span className="billing-label">Seats</span>
                  <span className="billing-value">
                    {billingData.seats_used} / {billingData.seats_total} used
                  </span>
                </div>
                {billingData.is_trial && billingData.trial_days_remaining !== null && (
                  <div className="billing-item">
                    <span className="billing-label">Trial Ends</span>
                    <span className="billing-value">
                      {formatDate(billingData.trial_ends_at)}
                      <span className="billing-subtext">
                        ({billingData.trial_days_remaining} days remaining)
                      </span>
                    </span>
                  </div>
                )}
                {billingData.has_stripe_subscription && billingData.next_billing_date && (
                  <div className="billing-item">
                    <span className="billing-label">Next Billing Date</span>
                    <span className="billing-value">
                      {formatDate(billingData.next_billing_date)}
                    </span>
                  </div>
                )}
                {billingData.billing_interval && (
                  <div className="billing-item">
                    <span className="billing-label">Billing Cycle</span>
                    <span className="billing-value">
                      {billingData.billing_interval === 'month' ? 'Monthly' : 'Annual'}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Contact Card */}
            <div className="card">
              <h2 className="card-title">Need to Make Changes?</h2>
              <p className="text-muted" style={{ marginBottom: '16px' }}>
                To modify your subscription, add seats, or discuss pricing options,
                please contact our sales team.
              </p>
              <a
                href={`mailto:${billingData.contact_email}?subject=Ilana Subscription Inquiry`}
                className="btn btn-primary"
              >
                Contact Sales
              </a>
              <p className="text-muted" style={{ marginTop: '12px', fontSize: '14px' }}>
                {billingData.contact_email}
              </p>
            </div>
          </>
        )}
      </main>

      <style jsx>{`
        .page-title {
          margin-bottom: 24px;
          font-size: 24px;
          font-weight: 600;
        }

        .billing-banner {
          padding: 12px 16px;
          border-radius: 8px;
          margin-bottom: 24px;
          font-weight: 500;
        }

        .billing-banner-trial {
          background: var(--gray-100);
          color: var(--gray-900);
          border: 1px solid var(--gray-200);
        }

        .billing-banner-active {
          background: #ecfdf5;
          color: #065f46;
          border: 1px solid #a7f3d0;
        }

        .billing-banner-past_due {
          background: #fffbeb;
          color: #92400e;
          border: 1px solid #fcd34d;
        }

        .billing-banner-expired,
        .billing-banner-cancelled {
          background: #fef2f2;
          color: #991b1b;
          border: 1px solid #fecaca;
        }

        .billing-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 24px;
        }

        .billing-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .billing-label {
          font-size: 13px;
          color: var(--gray-500);
          font-weight: 500;
        }

        .billing-value {
          font-size: 16px;
          color: var(--gray-900);
          font-weight: 500;
        }

        .billing-subtext {
          font-size: 13px;
          color: var(--gray-500);
          font-weight: 400;
          margin-left: 8px;
        }

        .status-badge {
          display: inline-block;
          padding: 4px 12px;
          border-radius: 9999px;
          font-size: 13px;
          font-weight: 500;
          width: fit-content;
        }

        .status-badge-active {
          background: #ecfdf5;
          color: #065f46;
        }

        .status-badge-trial {
          background: var(--gray-100);
          color: var(--gray-700);
        }

        .status-badge-warning {
          background: #fffbeb;
          color: #92400e;
        }

        .status-badge-error {
          background: #fef2f2;
          color: #991b1b;
        }

        .card-error {
          background: #fef2f2;
          border-color: #fecaca;
          color: #991b1b;
        }
      `}</style>
    </>
  );
}
