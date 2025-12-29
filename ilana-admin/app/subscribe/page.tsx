'use client';

import { useEffect, useState, useCallback, Suspense } from 'react';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { useSearchParams } from 'next/navigation';
import { apiRequest, loginRequest } from '@/lib/msal-config';
import {
  createCheckoutSession,
  requestInvoice,
  InvoiceRequestInput,
} from '@/lib/api';
import { isDevMode } from '@/lib/mock-data';

// Pricing constants
const PRICING = {
  corporate: {
    label: 'Corporate',
    description: 'For universities & non-profits',
    monthly: 75,
    annual: 750, // 10 months
  },
  enterprise: {
    label: 'Enterprise',
    description: 'For pharma, CRO, and biotech',
    monthly: 149,
    annual: 1490, // 10 months
  },
};

function SubscribeContent() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const searchParams = useSearchParams();

  // URL params
  const planParam = searchParams.get('plan') as 'corporate' | 'enterprise' | null;
  const orgParam = searchParams.get('org');
  const seatsParam = searchParams.get('seats');
  const invoiceParam = searchParams.get('invoice') === 'true';

  // State
  const [plan, setPlan] = useState<'corporate' | 'enterprise'>(planParam || 'enterprise');
  const [orgName, setOrgName] = useState(orgParam || '');
  const [seats, setSeats] = useState(parseInt(seatsParam || '10', 10));
  const [billingInterval, setBillingInterval] = useState<'month' | 'year'>('year');
  const [showInvoiceModal, setShowInvoiceModal] = useState(invoiceParam);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [invoiceSuccess, setInvoiceSuccess] = useState(false);
  const [trialExtendedTo, setTrialExtendedTo] = useState<string | null>(null);
  const [isDevSession, setIsDevSession] = useState(false);

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

  // Calculate pricing
  const pricing = PRICING[plan];
  const monthlyTotal = pricing.monthly * seats;
  const annualTotal = pricing.annual * seats;
  const annualSavings = (pricing.monthly * 12 - pricing.annual) * seats;
  const currentTotal = billingInterval === 'month' ? monthlyTotal : annualTotal;
  const currentPerSeat = billingInterval === 'month' ? pricing.monthly : pricing.annual;

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

  // Handle login and checkout
  const handleSubscribe = async () => {
    setActionError(null);

    // If not authenticated, trigger login first
    if (!isAuthenticated && !isDevSession && !isDevMode()) {
      try {
        await instance.loginRedirect({
          ...loginRequest,
          state: JSON.stringify({ plan, seats, billingInterval }),
        });
        return;
      } catch (e) {
        setActionError('Failed to start login. Please try again.');
        return;
      }
    }

    // Dev mode simulation
    if (isDevSession || isDevMode()) {
      alert(`In dev mode: Would redirect to Stripe Checkout for ${plan} plan, ${seats} seats, ${billingInterval}ly billing`);
      return;
    }

    // Create checkout session
    setActionLoading(true);
    try {
      const token = await getToken();
      if (!token) {
        setActionError('Unable to authenticate. Please sign in again.');
        return;
      }

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

    // Dev mode simulation
    if (isDevSession || isDevMode()) {
      setInvoiceSuccess(true);
      setTrialExtendedTo(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString());
      setShowInvoiceModal(false);
      return;
    }

    // If not authenticated, trigger login first
    if (!isAuthenticated) {
      try {
        await instance.loginRedirect({
          ...loginRequest,
          state: JSON.stringify({ invoice: true, plan, seats, billingInterval }),
        });
        return;
      } catch (e) {
        setActionError('Failed to start login. Please try again.');
        return;
      }
    }

    setActionLoading(true);
    setActionError(null);

    try {
      const token = await getToken();
      if (!token) {
        setActionError('Unable to authenticate. Please sign in again.');
        return;
      }

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

  return (
    <main className="subscribe-page">
      <div className="subscribe-container">
        {/* Header */}
        <div className="subscribe-header">
          <h1>Subscribe to Ilana</h1>
          <p>Prevent protocol amendments with AI-powered analysis</p>
        </div>

        {/* Success Message */}
        {invoiceSuccess && (
          <div className="success-banner">
            <svg className="success-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            <div>
              <strong>Invoice request submitted!</strong>
              <p>You will receive an invoice via email within 1-2 business days.
                {trialExtendedTo && (
                  <> Your trial has been extended to {formatDate(trialExtendedTo)} while we process your invoice.</>
                )}
              </p>
            </div>
          </div>
        )}

        {/* Plan Selection */}
        <div className="section">
          <h2>Select Your Plan</h2>
          <div className="plan-options">
            <button
              className={`plan-option ${plan === 'corporate' ? 'selected' : ''}`}
              onClick={() => setPlan('corporate')}
            >
              <div className="plan-badge">50% OFF</div>
              <div className="plan-name">{PRICING.corporate.label}</div>
              <div className="plan-price">{formatCurrency(PRICING.corporate.monthly)}/user/mo</div>
              <div className="plan-desc">{PRICING.corporate.description}</div>
            </button>
            <button
              className={`plan-option ${plan === 'enterprise' ? 'selected' : ''}`}
              onClick={() => setPlan('enterprise')}
            >
              <div className="plan-name">{PRICING.enterprise.label}</div>
              <div className="plan-price">{formatCurrency(PRICING.enterprise.monthly)}/user/mo</div>
              <div className="plan-desc">{PRICING.enterprise.description}</div>
            </button>
          </div>
        </div>

        {/* Organization & Seats */}
        <div className="section">
          <h2>Your Organization</h2>
          <div className="form-row">
            <div className="form-group">
              <label>Organization Name</label>
              <input
                type="text"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Your company name"
              />
            </div>
            <div className="form-group">
              <label>Number of Users</label>
              <select value={seats} onChange={(e) => setSeats(parseInt(e.target.value, 10))}>
                <option value="5">5 users</option>
                <option value="10">10 users</option>
                <option value="15">15 users</option>
                <option value="20">20 users</option>
                <option value="25">25 users</option>
                <option value="50">50 users</option>
                <option value="100">100 users</option>
              </select>
            </div>
          </div>
        </div>

        {/* Billing Frequency */}
        <div className="section">
          <h2>Billing Frequency</h2>
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
              <span className="savings-badge">Save {formatCurrency(annualSavings)}</span>
            </button>
          </div>
        </div>

        {/* Price Summary */}
        <div className="price-summary">
          <div className="price-main">
            {formatCurrency(currentTotal)}
            <span className="price-period">/{billingInterval === 'month' ? 'month' : 'year'}</span>
          </div>
          <div className="price-detail">
            {formatCurrency(currentPerSeat)} per user/{billingInterval === 'month' ? 'month' : 'year'} &times; {seats} users
          </div>
        </div>

        {/* Error Message */}
        {actionError && (
          <div className="error-message">{actionError}</div>
        )}

        {/* CTA Buttons */}
        <div className="cta-buttons">
          <button
            className="btn-primary"
            onClick={handleSubscribe}
            disabled={actionLoading}
          >
            {actionLoading ? 'Processing...' : 'Continue to Payment'}
            <span className="btn-subtitle">Credit Card via Stripe</span>
          </button>
          <button
            className="btn-secondary"
            onClick={() => setShowInvoiceModal(true)}
            disabled={actionLoading}
          >
            Request Invoice Instead
            <span className="btn-subtitle">NET 30/60 Terms</span>
          </button>
        </div>

        {/* Help Link */}
        <p className="help-text">
          Questions? <a href="mailto:sales@ilanaimmersive.com">Contact sales</a> or{' '}
          <a href="https://calendly.com/ilana-demo/30min" target="_blank" rel="noopener noreferrer">
            schedule a demo
          </a>
        </p>
      </div>

      {/* Invoice Request Modal */}
      {showInvoiceModal && (
        <div className="modal-overlay" onClick={() => setShowInvoiceModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">Request Invoice</h3>

            <div className="modal-body">
              <div className="invoice-summary">
                <div className="invoice-amount">
                  {formatCurrency(currentTotal)}
                  <span className="invoice-period">/{billingInterval === 'month' ? 'mo' : 'yr'}</span>
                </div>
                <div className="invoice-details">
                  {pricing.label} Plan - {seats} seats - {billingInterval === 'month' ? 'Monthly' : 'Annual'} billing
                </div>
              </div>

              <div className="form-section">
                <h4>Billing Contact</h4>
                <div className="form-row">
                  <div className="form-group">
                    <label>Contact Name <span className="required">*</span></label>
                    <input
                      type="text"
                      value={invoiceForm.billing_contact_name}
                      onChange={(e) => updateInvoiceField('billing_contact_name', e.target.value)}
                      placeholder="John Smith"
                    />
                  </div>
                  <div className="form-group">
                    <label>Contact Email <span className="required">*</span></label>
                    <input
                      type="email"
                      value={invoiceForm.billing_contact_email}
                      onChange={(e) => updateInvoiceField('billing_contact_email', e.target.value)}
                      placeholder="accounts-payable@company.com"
                    />
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h4>Billing Address</h4>
                <div className="form-group">
                  <label>Street Address <span className="required">*</span></label>
                  <textarea
                    value={invoiceForm.billing_address}
                    onChange={(e) => updateInvoiceField('billing_address', e.target.value)}
                    placeholder="123 Main Street&#10;Suite 400"
                    rows={2}
                  />
                </div>
                <div className="form-row form-row-3">
                  <div className="form-group">
                    <label>City <span className="required">*</span></label>
                    <input
                      type="text"
                      value={invoiceForm.billing_city}
                      onChange={(e) => updateInvoiceField('billing_city', e.target.value)}
                      placeholder="Boston"
                    />
                  </div>
                  <div className="form-group">
                    <label>State/Province <span className="required">*</span></label>
                    <input
                      type="text"
                      value={invoiceForm.billing_state}
                      onChange={(e) => updateInvoiceField('billing_state', e.target.value)}
                      placeholder="MA"
                    />
                  </div>
                  <div className="form-group">
                    <label>ZIP/Postal Code <span className="required">*</span></label>
                    <input
                      type="text"
                      value={invoiceForm.billing_zip}
                      onChange={(e) => updateInvoiceField('billing_zip', e.target.value)}
                      placeholder="02101"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Country</label>
                  <select
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
                <h4>Payment Details</h4>
                <div className="form-row">
                  <div className="form-group">
                    <label>PO Number</label>
                    <input
                      type="text"
                      value={invoiceForm.po_number}
                      onChange={(e) => updateInvoiceField('po_number', e.target.value)}
                      placeholder="Optional"
                    />
                  </div>
                  <div className="form-group">
                    <label>Payment Terms</label>
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
                  <label>Additional Notes</label>
                  <textarea
                    value={invoiceForm.notes}
                    onChange={(e) => updateInvoiceField('notes', e.target.value)}
                    placeholder="Any special billing instructions..."
                    rows={2}
                  />
                </div>
              </div>

              {actionError && (
                <div className="error-message">{actionError}</div>
              )}

              <p className="form-note">
                Your trial will be extended by 7 days while we process your invoice request.
              </p>
            </div>

            <div className="modal-actions">
              <button
                className="btn-cancel"
                onClick={() => setShowInvoiceModal(false)}
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                className="btn-submit"
                onClick={handleInvoiceRequest}
                disabled={actionLoading}
              >
                {actionLoading ? 'Submitting...' : 'Submit Invoice Request'}
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .subscribe-page {
          min-height: 100vh;
          background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
          padding: 40px 20px;
        }

        .subscribe-container {
          max-width: 600px;
          margin: 0 auto;
          background: white;
          border-radius: 16px;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
          padding: 40px;
        }

        .subscribe-header {
          text-align: center;
          margin-bottom: 32px;
        }

        .subscribe-header h1 {
          font-size: 28px;
          font-weight: 700;
          color: #1a1a1a;
          margin-bottom: 8px;
        }

        .subscribe-header p {
          color: #6b7280;
          font-size: 16px;
        }

        .success-banner {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 16px;
          background: #ecfdf5;
          border: 1px solid #a7f3d0;
          border-radius: 8px;
          margin-bottom: 24px;
        }

        .success-icon {
          width: 24px;
          height: 24px;
          color: #059669;
          flex-shrink: 0;
        }

        .success-banner strong {
          color: #065f46;
          display: block;
          margin-bottom: 4px;
        }

        .success-banner p {
          color: #047857;
          font-size: 14px;
          margin: 0;
        }

        .section {
          margin-bottom: 28px;
        }

        .section h2 {
          font-size: 14px;
          font-weight: 600;
          color: #374151;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 12px;
        }

        .plan-options {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }

        .plan-option {
          position: relative;
          padding: 20px;
          border: 2px solid #e5e7eb;
          border-radius: 12px;
          background: white;
          cursor: pointer;
          transition: all 0.2s;
          text-align: left;
        }

        .plan-option:hover {
          border-color: #9ca3af;
        }

        .plan-option.selected {
          border-color: #10b981;
          background: #ecfdf5;
        }

        .plan-badge {
          position: absolute;
          top: -10px;
          right: 12px;
          background: #10b981;
          color: white;
          font-size: 11px;
          font-weight: 600;
          padding: 4px 8px;
          border-radius: 4px;
        }

        .plan-name {
          font-size: 18px;
          font-weight: 600;
          color: #1a1a1a;
          margin-bottom: 4px;
        }

        .plan-price {
          font-size: 16px;
          color: #059669;
          font-weight: 500;
          margin-bottom: 4px;
        }

        .plan-desc {
          font-size: 13px;
          color: #6b7280;
        }

        .form-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }

        .form-row-3 {
          grid-template-columns: 2fr 1fr 1fr;
        }

        .form-group {
          margin-bottom: 16px;
        }

        .form-group label {
          display: block;
          font-size: 14px;
          font-weight: 500;
          color: #374151;
          margin-bottom: 6px;
        }

        .form-group input,
        .form-group select,
        .form-group textarea {
          width: 100%;
          padding: 10px 14px;
          border: 1px solid #d1d5db;
          border-radius: 8px;
          font-size: 15px;
          transition: border-color 0.2s;
        }

        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
          outline: none;
          border-color: #10b981;
          box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
        }

        .form-group textarea {
          resize: vertical;
          min-height: 60px;
          font-family: inherit;
        }

        .interval-toggle {
          display: flex;
          gap: 8px;
        }

        .interval-btn {
          flex: 1;
          padding: 14px 16px;
          border: 2px solid #e5e7eb;
          border-radius: 8px;
          background: white;
          font-size: 15px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
        }

        .interval-btn:hover {
          border-color: #9ca3af;
        }

        .interval-btn.active {
          border-color: #10b981;
          background: #ecfdf5;
          color: #065f46;
        }

        .savings-badge {
          font-size: 12px;
          color: #059669;
          font-weight: 600;
        }

        .price-summary {
          text-align: center;
          padding: 24px;
          background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
          border-radius: 12px;
          margin-bottom: 24px;
        }

        .price-main {
          font-size: 42px;
          font-weight: 700;
          color: #1a1a1a;
        }

        .price-period {
          font-size: 18px;
          font-weight: 400;
          color: #6b7280;
        }

        .price-detail {
          font-size: 14px;
          color: #6b7280;
          margin-top: 4px;
        }

        .error-message {
          background: #fef2f2;
          border: 1px solid #fecaca;
          color: #dc2626;
          padding: 12px 16px;
          border-radius: 8px;
          margin-bottom: 16px;
          font-size: 14px;
        }

        .cta-buttons {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .btn-primary,
        .btn-secondary {
          width: 100%;
          padding: 16px 24px;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          border: none;
        }

        .btn-primary {
          background: #10b981;
          color: white;
        }

        .btn-primary:hover:not(:disabled) {
          background: #059669;
        }

        .btn-secondary {
          background: white;
          color: #374151;
          border: 2px solid #d1d5db;
        }

        .btn-secondary:hover:not(:disabled) {
          border-color: #9ca3af;
          background: #f9fafb;
        }

        .btn-primary:disabled,
        .btn-secondary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-subtitle {
          font-size: 12px;
          font-weight: 400;
          opacity: 0.8;
        }

        .help-text {
          text-align: center;
          margin-top: 24px;
          font-size: 14px;
          color: #6b7280;
        }

        .help-text a {
          color: #10b981;
          text-decoration: none;
        }

        .help-text a:hover {
          text-decoration: underline;
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
          padding: 20px;
        }

        .modal {
          background: white;
          border-radius: 16px;
          width: 100%;
          max-width: 560px;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        }

        .modal-title {
          font-size: 20px;
          font-weight: 600;
          padding: 24px;
          border-bottom: 1px solid #e5e7eb;
          margin: 0;
        }

        .modal-body {
          padding: 24px;
        }

        .invoice-summary {
          background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          padding: 20px;
          margin-bottom: 24px;
          text-align: center;
        }

        .invoice-amount {
          font-size: 36px;
          font-weight: 700;
          color: #1a1a1a;
        }

        .invoice-period {
          font-size: 18px;
          font-weight: 400;
          color: #6b7280;
        }

        .invoice-details {
          font-size: 14px;
          color: #6b7280;
          margin-top: 4px;
        }

        .form-section {
          margin-bottom: 24px;
        }

        .form-section h4 {
          font-size: 14px;
          font-weight: 600;
          color: #374151;
          margin-bottom: 12px;
          padding-bottom: 8px;
          border-bottom: 1px solid #e5e7eb;
        }

        .required {
          color: #dc2626;
        }

        .payment-terms-toggle {
          display: flex;
          gap: 8px;
        }

        .terms-btn {
          flex: 1;
          padding: 10px 16px;
          border: 2px solid #e5e7eb;
          border-radius: 6px;
          background: white;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .terms-btn:hover {
          border-color: #9ca3af;
        }

        .terms-btn.active {
          border-color: #10b981;
          background: #ecfdf5;
          color: #065f46;
        }

        .form-note {
          font-size: 13px;
          color: #6b7280;
          margin-top: 16px;
          padding: 12px;
          background: #f0f9ff;
          border-radius: 8px;
          border: 1px solid #bae6fd;
        }

        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          padding: 20px 24px;
          border-top: 1px solid #e5e7eb;
        }

        .btn-cancel,
        .btn-submit {
          padding: 12px 24px;
          border-radius: 8px;
          font-size: 15px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn-cancel {
          background: white;
          border: 1px solid #d1d5db;
          color: #374151;
        }

        .btn-cancel:hover:not(:disabled) {
          background: #f9fafb;
        }

        .btn-submit {
          background: #10b981;
          border: none;
          color: white;
        }

        .btn-submit:hover:not(:disabled) {
          background: #059669;
        }

        .btn-cancel:disabled,
        .btn-submit:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        @media (max-width: 640px) {
          .subscribe-container {
            padding: 24px;
          }

          .plan-options {
            grid-template-columns: 1fr;
          }

          .form-row,
          .form-row-3 {
            grid-template-columns: 1fr;
          }

          .modal-actions {
            flex-direction: column-reverse;
          }

          .btn-cancel,
          .btn-submit {
            width: 100%;
          }
        }
      `}</style>
    </main>
  );
}

export default function SubscribePage() {
  return (
    <Suspense fallback={
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)'
      }}>
        <p>Loading...</p>
      </div>
    }>
      <SubscribeContent />
    </Suspense>
  );
}
