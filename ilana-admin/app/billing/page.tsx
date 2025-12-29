'use client';

import { useEffect, useState, useCallback } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { useRouter } from 'next/navigation';
import { apiRequest } from '@/lib/msal-config';
import {
  fetchBillingStatus,
  fetchConversionInfo,
  createCheckoutSession,
  requestInvoice,
  BillingStatus,
  ConversionInfo,
  InvoiceRequestInput,
} from '@/lib/api';
import { isDevMode, mockBillingStatus, mockConversionInfo } from '@/lib/mock-data';
import Header from '@/components/Header';

export default function BillingPage() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const router = useRouter();

  const [billingData, setBillingData] = useState<BillingStatus | null>(null);
  const [conversionInfo, setConversionInfo] = useState<ConversionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDevSession, setIsDevSession] = useState(false);

  // Conversion UI state
  const [billingInterval, setBillingInterval] = useState<'month' | 'year'>('year');
  const [showInvoiceModal, setShowInvoiceModal] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [invoiceSuccess, setInvoiceSuccess] = useState(false);
  const [trialExtendedTo, setTrialExtendedTo] = useState<string | null>(null);

  // Invoice form state
  const [invoiceForm, setInvoiceForm] = useState({
    billing_contact_name: '',
    billing_contact_email: '',
    billing_address: '',
    billing_city: '',
    billing_state: '',
    billing_zip: '',
    billing_country: 'United States',
    po_number: '',
    payment_terms: 'net_30' as 'net_30' | 'net_60',
    notes: '',
  });

  // Countries list
  const countries = [
    'United States',
    'Canada',
    'United Kingdom',
    'Germany',
    'France',
    'Australia',
    'Switzerland',
    'Netherlands',
    'Belgium',
    'Ireland',
    'Other',
  ];

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
        setConversionInfo(mockConversionInfo);
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

        // Fetch billing data and conversion info in parallel
        const [billing, conversion] = await Promise.all([
          fetchBillingStatus({ token }),
          fetchConversionInfo({ token }).catch(() => null),
        ]);
        setBillingData(billing);
        setConversionInfo(conversion);
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

  // Handle checkout (credit card)
  const handleCheckout = async () => {
    if (isDevSession || isDevMode()) {
      alert('In dev mode: Would redirect to Stripe Checkout');
      return;
    }

    setActionLoading(true);
    setActionError(null);

    try {
      const token = await getToken();
      if (!token) throw new Error('Unable to authenticate');

      const result = await createCheckoutSession(billingInterval, { token });
      window.location.href = result.checkout_url;
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to create checkout session');
    } finally {
      setActionLoading(false);
    }
  };

  // Validate invoice form
  const validateInvoiceForm = (): string | null => {
    if (!invoiceForm.billing_contact_name.trim()) return 'Billing contact name is required';
    if (!invoiceForm.billing_contact_email.trim()) return 'Billing contact email is required';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(invoiceForm.billing_contact_email)) return 'Invalid email address';
    if (!invoiceForm.billing_address.trim()) return 'Billing address is required';
    if (!invoiceForm.billing_city.trim()) return 'City is required';
    if (!invoiceForm.billing_state.trim()) return 'State/Province is required';
    if (!invoiceForm.billing_zip.trim()) return 'ZIP/Postal code is required';
    return null;
  };

  // Handle invoice request
  const handleInvoiceRequest = async () => {
    const validationError = validateInvoiceForm();
    if (validationError) {
      setActionError(validationError);
      return;
    }

    if (isDevSession || isDevMode()) {
      setInvoiceSuccess(true);
      setTrialExtendedTo(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString());
      setShowInvoiceModal(false);
      return;
    }

    setActionLoading(true);
    setActionError(null);

    try {
      const token = await getToken();
      if (!token) throw new Error('Unable to authenticate');

      const input: InvoiceRequestInput = {
        billing_interval: billingInterval,
        billing_contact_name: invoiceForm.billing_contact_name.trim(),
        billing_contact_email: invoiceForm.billing_contact_email.trim(),
        billing_address: invoiceForm.billing_address.trim(),
        billing_city: invoiceForm.billing_city.trim(),
        billing_state: invoiceForm.billing_state.trim(),
        billing_zip: invoiceForm.billing_zip.trim(),
        billing_country: invoiceForm.billing_country,
        payment_terms: invoiceForm.payment_terms,
        po_number: invoiceForm.po_number.trim() || undefined,
        notes: invoiceForm.notes.trim() || undefined,
      };

      const result = await requestInvoice(input, { token });
      setInvoiceSuccess(true);
      setTrialExtendedTo(result.trial_extended_to);
      setShowInvoiceModal(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to request invoice');
    } finally {
      setActionLoading(false);
    }
  };

  // Update invoice form field
  const updateInvoiceField = (field: keyof typeof invoiceForm, value: string) => {
    setInvoiceForm(prev => ({ ...prev, [field]: value }));
    if (actionError) setActionError(null);
  };

  // Format currency
  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
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

  // Check if we should show conversion options
  const showConversion = billingData &&
    (billingData.is_trial || billingData.status === 'expired') &&
    !billingData.has_stripe_subscription &&
    conversionInfo;

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

            {/* Invoice Success Message */}
            {invoiceSuccess && (
              <div className="billing-banner billing-banner-active">
                <span>
                  Invoice request submitted successfully. You will receive an invoice via email within 1-2 business days.
                  {trialExtendedTo && (
                    <> Your trial has been extended to {formatDate(trialExtendedTo)} while we process your invoice.</>
                  )}
                </span>
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
                    {conversionInfo ? conversionInfo.plan_label : (billingData.is_trial ? 'Free Trial' : 'Ilana Pro')}
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

            {/* Conversion Card - Show for trials */}
            {showConversion && conversionInfo && (
              <div className="card conversion-card">
                <h2 className="card-title">
                  {conversionInfo.trial_status.is_expired
                    ? 'Your trial has ended'
                    : 'Subscribe to Ilana'}
                </h2>

                {/* Discount Banner */}
                {conversionInfo.is_discount_applied && (
                  <div className="discount-banner">
                    <span className="discount-icon">&#127891;</span>
                    <div className="discount-text">
                      <strong>Education/Non-Profit Discount Applied</strong>
                      <span>{conversionInfo.discount_reason || 'Your organization qualifies for discounted pricing (50% off)'}</span>
                    </div>
                  </div>
                )}

                <div className="plan-summary">
                  <div className="plan-info">
                    <span className="plan-name">{conversionInfo.plan_label} Plan</span>
                    <span className="plan-seats">{conversionInfo.seats} seats</span>
                  </div>
                </div>

                {/* Billing interval toggle */}
                <div className="interval-toggle">
                  <button
                    className={`interval-btn ${billingInterval === 'month' ? 'active' : ''}`}
                    onClick={() => setBillingInterval('month')}
                  >
                    Monthly
                  </button>
                  <button
                    className={`interval-btn ${billingInterval === 'year' ? 'active' : ''}`}
                    onClick={() => setBillingInterval('year')}
                  >
                    Annual
                    <span className="savings-badge">Save {formatCurrency(conversionInfo.pricing.annual_savings)}</span>
                  </button>
                </div>

                {/* Pricing display */}
                <div className="pricing-display">
                  <div className="price-main">
                    {billingInterval === 'month'
                      ? formatCurrency(conversionInfo.pricing.monthly_total)
                      : formatCurrency(conversionInfo.pricing.annual_total)}
                    <span className="price-period">
                      /{billingInterval === 'month' ? 'month' : 'year'}
                    </span>
                  </div>
                  <div className="price-detail">
                    {formatCurrency(billingInterval === 'month'
                      ? conversionInfo.pricing.monthly_per_seat
                      : conversionInfo.pricing.annual_per_seat
                    )} per user/{billingInterval === 'month' ? 'month' : 'year'}
                  </div>
                </div>

                {/* Action error */}
                {actionError && (
                  <div className="action-error">{actionError}</div>
                )}

                {/* Conversion buttons */}
                <div className="conversion-buttons">
                  <button
                    className="btn btn-primary btn-large"
                    onClick={handleCheckout}
                    disabled={actionLoading}
                  >
                    {actionLoading ? 'Processing...' : 'Subscribe Now'}
                    <span className="btn-subtitle">Credit Card</span>
                  </button>

                  <button
                    className="btn btn-secondary btn-large"
                    onClick={() => setShowInvoiceModal(true)}
                    disabled={actionLoading}
                  >
                    Request Invoice
                    <span className="btn-subtitle">NET 30</span>
                  </button>

                  <a
                    href={`mailto:${billingData.contact_email}?subject=Ilana Demo Request - ${conversionInfo.plan_label} Plan`}
                    className="btn btn-outline btn-large"
                  >
                    Schedule Demo
                    <span className="btn-subtitle">Talk to Sales</span>
                  </a>
                </div>
              </div>
            )}

            {/* Contact Card (for active subscriptions or when conversion not available) */}
            {!showConversion && (
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
            )}
          </>
        )}

        {/* Invoice Request Modal */}
        {showInvoiceModal && conversionInfo && (
          <div className="modal-overlay" onClick={() => setShowInvoiceModal(false)}>
            <div className="modal modal-large" onClick={(e) => e.stopPropagation()}>
              <h3 className="modal-title">Request Invoice</h3>

              <div className="modal-body">
                <div className="invoice-summary">
                  <div className="invoice-amount">
                    {formatCurrency(
                      billingInterval === 'month'
                        ? conversionInfo.pricing.monthly_total
                        : conversionInfo.pricing.annual_total
                    )}
                    <span className="invoice-period">/{billingInterval === 'month' ? 'mo' : 'yr'}</span>
                  </div>
                  <div className="invoice-details">
                    {conversionInfo.plan_label} Plan - {conversionInfo.seats} seats - {billingInterval === 'month' ? 'Monthly' : 'Annual'} billing
                  </div>
                </div>

                <div className="form-section">
                  <h4 className="form-section-title">Billing Contact</h4>
                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">Contact Name <span className="required">*</span></label>
                      <input
                        type="text"
                        className="form-input"
                        value={invoiceForm.billing_contact_name}
                        onChange={(e) => updateInvoiceField('billing_contact_name', e.target.value)}
                        placeholder="John Smith"
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Contact Email <span className="required">*</span></label>
                      <input
                        type="email"
                        className="form-input"
                        value={invoiceForm.billing_contact_email}
                        onChange={(e) => updateInvoiceField('billing_contact_email', e.target.value)}
                        placeholder="accounts-payable@company.com"
                      />
                    </div>
                  </div>
                </div>

                <div className="form-section">
                  <h4 className="form-section-title">Billing Address</h4>
                  <div className="form-group">
                    <label className="form-label">Street Address <span className="required">*</span></label>
                    <textarea
                      className="form-input form-textarea"
                      value={invoiceForm.billing_address}
                      onChange={(e) => updateInvoiceField('billing_address', e.target.value)}
                      placeholder="123 Main Street&#10;Suite 400"
                      rows={2}
                    />
                  </div>
                  <div className="form-row form-row-3">
                    <div className="form-group">
                      <label className="form-label">City <span className="required">*</span></label>
                      <input
                        type="text"
                        className="form-input"
                        value={invoiceForm.billing_city}
                        onChange={(e) => updateInvoiceField('billing_city', e.target.value)}
                        placeholder="Boston"
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">State/Province <span className="required">*</span></label>
                      <input
                        type="text"
                        className="form-input"
                        value={invoiceForm.billing_state}
                        onChange={(e) => updateInvoiceField('billing_state', e.target.value)}
                        placeholder="MA"
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">ZIP/Postal Code <span className="required">*</span></label>
                      <input
                        type="text"
                        className="form-input"
                        value={invoiceForm.billing_zip}
                        onChange={(e) => updateInvoiceField('billing_zip', e.target.value)}
                        placeholder="02101"
                      />
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Country</label>
                    <select
                      className="form-input form-select"
                      value={invoiceForm.billing_country}
                      onChange={(e) => updateInvoiceField('billing_country', e.target.value)}
                    >
                      {countries.map(country => (
                        <option key={country} value={country}>{country}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="form-section">
                  <h4 className="form-section-title">Payment Details</h4>
                  <div className="form-row">
                    <div className="form-group">
                      <label className="form-label">PO Number</label>
                      <input
                        type="text"
                        className="form-input"
                        value={invoiceForm.po_number}
                        onChange={(e) => updateInvoiceField('po_number', e.target.value)}
                        placeholder="Optional"
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Payment Terms</label>
                      <div className="payment-terms-toggle">
                        <button
                          type="button"
                          className={`terms-btn ${invoiceForm.payment_terms === 'net_30' ? 'active' : ''}`}
                          onClick={() => updateInvoiceField('payment_terms', 'net_30')}
                        >
                          NET 30
                        </button>
                        <button
                          type="button"
                          className={`terms-btn ${invoiceForm.payment_terms === 'net_60' ? 'active' : ''}`}
                          onClick={() => updateInvoiceField('payment_terms', 'net_60')}
                        >
                          NET 60
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Additional Notes</label>
                    <textarea
                      className="form-input form-textarea"
                      value={invoiceForm.notes}
                      onChange={(e) => updateInvoiceField('notes', e.target.value)}
                      placeholder="Any special billing instructions or requirements..."
                      rows={2}
                    />
                  </div>
                </div>

                {actionError && (
                  <div className="action-error">{actionError}</div>
                )}

                <p className="form-note">
                  Your trial will be extended by 7 days while we process your invoice request.
                </p>
              </div>

              <div className="modal-actions">
                <button
                  className="btn btn-secondary"
                  onClick={() => setShowInvoiceModal(false)}
                  disabled={actionLoading}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleInvoiceRequest}
                  disabled={actionLoading}
                >
                  {actionLoading ? 'Submitting...' : 'Submit Invoice Request'}
                </button>
              </div>
            </div>
          </div>
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

        /* Conversion Card Styles */
        .conversion-card {
          background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
          border: 2px solid var(--gray-200);
        }

        .discount-banner {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 16px;
          background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
          border: 1px solid #a7f3d0;
          border-radius: 8px;
          margin-bottom: 20px;
        }

        .discount-icon {
          font-size: 24px;
          flex-shrink: 0;
        }

        .discount-text {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .discount-text strong {
          color: #065f46;
          font-size: 15px;
        }

        .discount-text span {
          color: #047857;
          font-size: 13px;
        }

        .plan-summary {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }

        .plan-info {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .plan-name {
          font-size: 18px;
          font-weight: 600;
          color: var(--gray-900);
        }

        .plan-seats {
          font-size: 14px;
          color: var(--gray-600);
        }

        .interval-toggle {
          display: flex;
          gap: 8px;
          margin-bottom: 24px;
        }

        .interval-btn {
          flex: 1;
          padding: 12px 16px;
          border: 2px solid var(--gray-200);
          border-radius: 8px;
          background: white;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
        }

        .interval-btn:hover {
          border-color: var(--gray-300);
        }

        .interval-btn.active {
          border-color: #2563eb;
          background: #eff6ff;
          color: #1d4ed8;
        }

        .savings-badge {
          font-size: 11px;
          color: #059669;
          font-weight: 600;
        }

        .pricing-display {
          text-align: center;
          margin-bottom: 24px;
          padding: 16px;
          background: white;
          border-radius: 8px;
        }

        .price-main {
          font-size: 36px;
          font-weight: 700;
          color: var(--gray-900);
        }

        .price-period {
          font-size: 18px;
          font-weight: 400;
          color: var(--gray-500);
        }

        .price-detail {
          font-size: 14px;
          color: var(--gray-600);
          margin-top: 4px;
        }

        .action-error {
          background: #fef2f2;
          border: 1px solid #fecaca;
          color: #991b1b;
          padding: 12px;
          border-radius: 8px;
          margin-bottom: 16px;
          font-size: 14px;
        }

        .conversion-buttons {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .btn-large {
          padding: 16px 24px;
          font-size: 16px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
        }

        .btn-subtitle {
          font-size: 12px;
          font-weight: 400;
          opacity: 0.8;
        }

        .btn-outline {
          background: white;
          border: 2px solid var(--gray-300);
          color: var(--gray-700);
        }

        .btn-outline:hover {
          background: var(--gray-50);
          border-color: var(--gray-400);
        }

        /* Modal Styles */
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .modal {
          background: white;
          border-radius: 12px;
          width: 100%;
          max-width: 480px;
          margin: 24px;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        }

        .modal-title {
          font-size: 18px;
          font-weight: 600;
          padding: 20px 24px;
          border-bottom: 1px solid var(--gray-200);
        }

        .modal-body {
          padding: 24px;
        }

        .modal-description {
          color: var(--gray-600);
          margin-bottom: 20px;
          font-size: 14px;
          line-height: 1.5;
        }

        .form-group {
          margin-bottom: 16px;
        }

        .form-label {
          display: block;
          font-size: 14px;
          font-weight: 500;
          color: var(--gray-700);
          margin-bottom: 6px;
        }

        .form-input {
          width: 100%;
          padding: 10px 12px;
          border: 1px solid var(--gray-300);
          border-radius: 6px;
          font-size: 14px;
          transition: border-color 0.2s;
        }

        .form-input:focus {
          outline: none;
          border-color: #2563eb;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
        }

        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          padding: 16px 24px;
          border-top: 1px solid var(--gray-200);
        }

        /* Large modal for invoice form */
        .modal-large {
          max-width: 600px;
          max-height: 90vh;
          overflow-y: auto;
        }

        .invoice-summary {
          background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
          border: 1px solid var(--gray-200);
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 24px;
          text-align: center;
        }

        .invoice-amount {
          font-size: 32px;
          font-weight: 700;
          color: var(--gray-900);
        }

        .invoice-period {
          font-size: 16px;
          font-weight: 400;
          color: var(--gray-500);
        }

        .invoice-details {
          font-size: 14px;
          color: var(--gray-600);
          margin-top: 4px;
        }

        .form-section {
          margin-bottom: 24px;
        }

        .form-section-title {
          font-size: 14px;
          font-weight: 600;
          color: var(--gray-800);
          margin-bottom: 12px;
          padding-bottom: 8px;
          border-bottom: 1px solid var(--gray-200);
        }

        .form-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }

        .form-row-3 {
          grid-template-columns: 2fr 1fr 1fr;
        }

        .required {
          color: #dc2626;
        }

        .form-textarea {
          resize: vertical;
          min-height: 60px;
          font-family: inherit;
        }

        .form-select {
          appearance: none;
          background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
          background-position: right 8px center;
          background-repeat: no-repeat;
          background-size: 20px 20px;
          padding-right: 36px;
        }

        .payment-terms-toggle {
          display: flex;
          gap: 8px;
        }

        .terms-btn {
          flex: 1;
          padding: 10px 16px;
          border: 2px solid var(--gray-200);
          border-radius: 6px;
          background: white;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .terms-btn:hover {
          border-color: var(--gray-300);
        }

        .terms-btn.active {
          border-color: #2563eb;
          background: #eff6ff;
          color: #1d4ed8;
        }

        .form-note {
          font-size: 13px;
          color: var(--gray-500);
          margin-top: 16px;
          padding: 12px;
          background: #f0f9ff;
          border-radius: 6px;
          border: 1px solid #bae6fd;
        }

        @media (max-width: 640px) {
          .form-row,
          .form-row-3 {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </>
  );
}
