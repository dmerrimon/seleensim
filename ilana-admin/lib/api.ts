/**
 * API Client for Ilana Backend
 *
 * Handles authenticated requests to the admin endpoints
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://ilanalabs-add-in.onrender.com';
const DEFAULT_TIMEOUT_MS = 30000; // 30 seconds

interface ApiOptions {
  token: string;
  signal?: AbortSignal;
}

interface User {
  id: string;
  email: string | null;
  display_name: string | null;
  is_admin: boolean;
  last_active_at: string | null;
  has_seat: boolean;
  seat_assigned_at: string | null;
}

interface Subscription {
  plan_type: string;
  seats_total: number;
  seats_used: number;
  seats_available: number;
}

interface Stats {
  total_users: number;
  users_with_seats: number;
  inactive_users: number;
  inactive_threshold_days: number;
}

interface Trial {
  status: 'trial' | 'expired' | 'blocked' | 'active';
  is_trial: boolean;
  days_remaining: number | null;
  grace_days_remaining?: number | null;
  ends_at?: string | null;
  message: string;
}

export interface DashboardData {
  tenant: {
    id: string;
    name: string | null;
  };
  subscription: Subscription;
  users: User[];
  stats: Stats;
  trial?: Trial;
}

export interface SeatActionResult {
  success: boolean;
  seats_used?: number;
  seats_total?: number;
  user_email?: string;
  error?: string;
}

export interface TransferAdminResult {
  success: boolean;
  previous_admin?: { id: string; email: string };
  new_admin?: { id: string; email: string };
  error?: string;
}

interface ApiError {
  detail?: string;
  message?: string;
}

/**
 * Create an AbortController with timeout
 * Returns the controller and a cleanup function to clear the timeout
 */
function createTimeoutController(timeoutMs: number = DEFAULT_TIMEOUT_MS): {
  controller: AbortController;
  cleanup: () => void;
} {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  return {
    controller,
    cleanup: () => clearTimeout(timeoutId),
  };
}

/**
 * Extract error message from various error types
 */
function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    if (error.name === 'AbortError') {
      return 'Request timed out. Please try again.';
    }
    return error.message;
  }
  return 'An unexpected error occurred';
}

/**
 * Fetch dashboard data (user list + stats)
 */
export async function fetchDashboard(options: ApiOptions): Promise<DashboardData> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/admin/users`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Revoke a user's seat
 */
export async function revokeUserSeat(
  userId: string,
  options: ApiOptions
): Promise<SeatActionResult> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/revoke`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Restore a user's seat
 */
export async function restoreUserSeat(
  userId: string,
  options: ApiOptions
): Promise<SeatActionResult> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/restore`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Transfer admin role to another user
 * The current admin will lose their admin privileges
 */
export async function transferAdmin(
  userId: string,
  options: ApiOptions
): Promise<TransferAdminResult> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/make-admin`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Billing status from the backend
 */
export interface BillingStatus {
  status: 'trial' | 'active' | 'past_due' | 'cancelled' | 'expired';
  plan_type: string;
  seats_used: number;
  seats_total: number;
  is_trial: boolean;
  trial_days_remaining: number | null;
  trial_ends_at: string | null;
  has_stripe_subscription: boolean;
  next_billing_date: string | null;
  billing_interval: 'month' | 'year' | null;
  contact_email: string;
  message: string | null;
  // B2B fields
  org_type?: string;  // pharmaceutical, cro, biotech, university, nonprofit
  detected_plan?: string;  // corporate or enterprise
}

/**
 * B2B Conversion info for trial-to-paid conversion
 */
export interface ConversionInfo {
  plan: 'corporate' | 'enterprise';
  plan_label: string;
  seats: number;
  pricing: {
    monthly_per_seat: number;
    annual_per_seat: number;
    monthly_total: number;
    annual_total: number;
    annual_savings: number;
  };
  trial_status: {
    is_trial: boolean;
    days_remaining: number | null;
    trial_ends_at: string | null;
    is_expired: boolean;
  };
  // Discount/verification info
  email_domain?: string;
  org_type?: string;
  is_discount_applied: boolean;
  is_verified: boolean;
  needs_review: boolean;
  discount_reason?: string;
}

/**
 * Checkout session response
 */
export interface CheckoutSessionResponse {
  checkout_url: string;
  session_id: string;
}

/**
 * Invoice request input (full form)
 */
export interface InvoiceRequestInput {
  billing_interval: 'month' | 'year';
  billing_contact_name: string;
  billing_contact_email: string;
  billing_address: string;
  billing_city: string;
  billing_state: string;
  billing_zip: string;
  billing_country: string;
  po_number?: string;
  payment_terms: 'net_30' | 'net_60';
  notes?: string;
}

/**
 * Invoice request response
 */
export interface InvoiceRequestResponse {
  success: boolean;
  message: string;
  invoice_request_id: string;
  trial_extended_to: string;
}

/**
 * Fetch billing status for the tenant
 */
export async function fetchBillingStatus(options: ApiOptions): Promise<BillingStatus> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/billing/status`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Fetch conversion info for B2B trial-to-paid conversion
 */
export async function fetchConversionInfo(options: ApiOptions): Promise<ConversionInfo> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/billing/conversion-info`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Create a Stripe Checkout session for subscription
 */
export async function createCheckoutSession(
  billingInterval: 'month' | 'year',
  options: ApiOptions
): Promise<CheckoutSessionResponse> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/billing/checkout`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ billing_interval: billingInterval }),
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Request invoice billing instead of credit card
 */
export async function requestInvoice(
  input: InvoiceRequestInput,
  options: ApiOptions
): Promise<InvoiceRequestResponse> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/billing/request-invoice`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(input),
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Validate current user's session
 */
export async function validateSession(options: ApiOptions): Promise<{
  status: string;
  user: { id: string; email: string; name: string; is_admin: boolean; is_super_admin: boolean } | null;
}> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/validate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

// =============================================================================
// Super Admin Types
// =============================================================================

export interface TenantSummary {
  id: string;
  name: string | null;
  azure_tenant_id: string;
  created_at: string;
  user_count: number;
  seats_used: number;
  seats_total: number;
  subscription_status: string;
  trial_days_remaining: number | null;
  has_stripe_subscription: boolean;
}

export interface TenantUser {
  id: string;
  email: string | null;
  display_name: string | null;
  is_admin: boolean;
  has_seat: boolean;
  last_active_at: string | null;
  created_at: string;
}

export interface TenantDetail {
  id: string;
  name: string | null;
  azure_tenant_id: string;
  created_at: string;
  subscription: {
    id: string;
    plan_type: string;
    status: string;
    seats_total: number;
    seats_used: number;
    trial_started_at: string | null;
    trial_ends_at: string | null;
    trial_days_remaining: number | null;
    converted_at: string | null;
    stripe_customer_id: string | null;
    stripe_subscription_id: string | null;
    has_stripe: boolean;
  };
  users: TenantUser[];
  audit_summary: {
    total_events: number;
    events_last_7_days: number;
  };
}

export interface SuperAdminStats {
  total_tenants: number;
  total_users: number;
  active_subscriptions: number;
  trials_active: number;
  mrr: number;
}

export interface UserSearchResult {
  id: string;
  email: string | null;
  display_name: string | null;
  tenant_id: string;
  tenant_name: string | null;
  is_admin: boolean;
  is_super_admin: boolean;
  has_seat: boolean;
  last_active_at: string | null;
}

export interface SuperAdminInfo {
  id: string;
  email: string | null;
  display_name: string | null;
  tenant_id: string;
  tenant_name: string | null;
}

// =============================================================================
// Super Admin API Functions
// =============================================================================

/**
 * Fetch all tenants (super admin only)
 */
export async function fetchAllTenants(options: ApiOptions): Promise<TenantSummary[]> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/tenants`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Fetch tenant detail (super admin only)
 */
export async function fetchTenantDetail(
  tenantId: string,
  options: ApiOptions
): Promise<TenantDetail> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/tenants/${tenantId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Search users by email across all tenants (super admin only)
 */
export async function searchUsers(
  email: string,
  options: ApiOptions
): Promise<UserSearchResult[]> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/super-admin/users/search?email=${encodeURIComponent(email)}`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${options.token}`,
          'Content-Type': 'application/json',
        },
        signal: options.signal || controller.signal,
      }
    );

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Extend a tenant's trial period (super admin only)
 */
export async function extendTrial(
  tenantId: string,
  days: number,
  options: ApiOptions
): Promise<{ success: boolean; new_trial_end: string }> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/super-admin/tenants/${tenantId}/extend-trial`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${options.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ days }),
        signal: options.signal || controller.signal,
      }
    );

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Fetch platform-wide statistics (super admin only)
 */
export async function fetchSuperAdminStats(options: ApiOptions): Promise<SuperAdminStats> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/stats`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Fetch list of all super admins (super admin only)
 */
export async function fetchSuperAdmins(options: ApiOptions): Promise<SuperAdminInfo[]> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/super-admins`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Grant super admin role to a user by email (super admin only)
 */
export async function grantSuperAdmin(
  email: string,
  options: ApiOptions
): Promise<{ success: boolean; user: SuperAdminInfo }> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/super-admins`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email }),
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

/**
 * Revoke super admin role from a user (super admin only)
 */
export async function revokeSuperAdmin(
  userId: string,
  options: ApiOptions
): Promise<{ success: boolean }> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/super-admins/${userId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}
