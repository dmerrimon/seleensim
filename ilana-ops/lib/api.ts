/**
 * API Client for Ilana Backend - Ops Portal
 *
 * Handles authenticated requests to the super admin endpoints
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://ilanalabs-add-in.onrender.com';
const DEFAULT_TIMEOUT_MS = 30000; // 30 seconds

interface ApiOptions {
  token: string;
  signal?: AbortSignal;
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

// =============================================================================
// Types
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

export interface ActivityLogEntry {
  id: string;
  tenant_id: string;
  tenant_name: string | null;
  user_id: string | null;
  user_email: string | null;
  action: string;
  details: string | null;
  created_at: string;
}

export interface AnalyticsData {
  signups_by_day: { date: string; count: number }[];
  active_users_by_day: { date: string; count: number }[];
  trials_converted: number;
  trials_expired: number;
  avg_trial_duration_days: number;
  top_tenants_by_users: { tenant_name: string; user_count: number }[];
}

// =============================================================================
// API Functions
// =============================================================================

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

/**
 * Update tenant information (name, notes, tags)
 */
export async function updateTenant(
  tenantId: string,
  data: { name?: string; notes?: string; tags?: string[] },
  options: ApiOptions
): Promise<{ success: boolean; tenant_id: string; name: string }> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/tenants/${tenantId}`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
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
 * Update seat count for a tenant
 * Now with real Stripe API integration - updates quantity in Stripe!
 */
export async function updateSeatCount(
  tenantId: string,
  seatCount: number,
  options: ApiOptions
): Promise<{ success: boolean; old_seats: number; new_seats: number; stripe_updated?: boolean; stripe_error?: string | null }> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/tenants/${tenantId}/seats`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ seat_count: seatCount }),
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
 * Manage subscription (cancel, activate, convert to paid)
 * Now with real Stripe API integration!
 */
export async function manageSubscription(
  tenantId: string,
  action: 'cancel' | 'cancel_immediately' | 'activate' | 'convert_to_paid',
  options: ApiOptions,
  planType?: string
): Promise<{ success: boolean; status: string; plan_type: string; stripe_updated?: boolean; stripe_error?: string | null }> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/tenants/${tenantId}/subscription`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ action, plan_type: planType }),
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
 * Manage user seat (revoke or restore) - cross-tenant
 */
export async function manageUserSeat(
  userId: string,
  action: 'revoke' | 'restore',
  options: ApiOptions
): Promise<{ success: boolean; action?: string; error?: string }> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/users/${userId}/seat`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ action }),
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
 * Fetch activity logs
 */
export async function fetchActivityLogs(
  options: ApiOptions,
  params?: { limit?: number; offset?: number; tenant_id?: string }
): Promise<ActivityLogEntry[]> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());
    if (params?.tenant_id) searchParams.set('tenant_id', params.tenant_id);

    const url = `${API_BASE_URL}/api/super-admin/activity-logs${searchParams.toString() ? `?${searchParams}` : ''}`;

    const response = await fetch(url, {
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
 * Fetch analytics data
 */
export async function fetchAnalytics(
  options: ApiOptions,
  days: number = 30
): Promise<AnalyticsData> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/analytics?days=${days}`, {
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
 * Export data as CSV or JSON
 */
export async function exportData(
  type: 'tenants' | 'users',
  format: 'json' | 'csv',
  options: ApiOptions,
  tenantId?: string
): Promise<Blob | object[]> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const params = new URLSearchParams({ format });
    if (tenantId) params.set('tenant_id', tenantId);

    const response = await fetch(`${API_BASE_URL}/api/super-admin/export/${type}?${params}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${options.token}`,
      },
      signal: options.signal || controller.signal,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    if (format === 'csv') {
      return response.blob();
    }
    return response.json();
  } catch (error) {
    throw new Error(getErrorMessage(error));
  } finally {
    cleanup();
  }
}

// =============================================================================
// Stripe Management Types & Functions
// =============================================================================

export interface StripeDetails {
  has_stripe: boolean;
  message?: string;
  subscription?: {
    id: string;
    status: string;
    current_period_start: number;
    current_period_end: number;
    cancel_at_period_end: boolean;
    canceled_at: number | null;
    created: number;
    quantity: number;
    plan: {
      id: string | null;
      amount: number | null;
      interval: string | null;
    };
  };
  customer?: {
    id: string;
    email: string | null;
    name: string | null;
    created: number;
  };
  payment_method?: {
    type: string;
    brand: string;
    last4: string;
    exp_month: number;
    exp_year: number;
  } | null;
  latest_invoice?: {
    id: string;
    status: string;
    amount_due: number;
    amount_paid: number;
    created: number;
    hosted_invoice_url: string | null;
    invoice_pdf: string | null;
  } | null;
}

export interface StripeInvoice {
  id: string;
  number: string | null;
  status: string;
  amount_due: number;
  amount_paid: number;
  currency: string;
  created: number;
  period_start: number | null;
  period_end: number | null;
  hosted_invoice_url: string | null;
  invoice_pdf: string | null;
}

export interface RefundResult {
  success: boolean;
  refund: {
    id: string;
    amount: number;
    currency: string;
    status: string;
    created: number;
  };
}

export interface SyncResult {
  success: boolean;
  changes: {
    status: { old: string; new: string };
    seats: { old: number; new: number };
  };
  stripe_status: string;
}

/**
 * Fetch detailed Stripe information for a tenant
 */
export async function fetchStripeDetails(
  tenantId: string,
  options: ApiOptions
): Promise<StripeDetails> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/tenants/${tenantId}/stripe`, {
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
 * Fetch invoice history from Stripe for a tenant
 */
export async function fetchStripeInvoices(
  tenantId: string,
  options: ApiOptions,
  limit: number = 10
): Promise<{ invoices: StripeInvoice[]; message?: string }> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/super-admin/tenants/${tenantId}/stripe/invoices?limit=${limit}`,
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
 * Issue a refund for the latest paid invoice
 */
export async function issueRefund(
  tenantId: string,
  options: ApiOptions,
  amountCents?: number,
  reason?: string
): Promise<RefundResult> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/tenants/${tenantId}/stripe/refund`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        amount_cents: amountCents,
        reason,
      }),
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
 * Sync local subscription data with Stripe
 */
export async function syncStripeSubscription(
  tenantId: string,
  options: ApiOptions
): Promise<SyncResult> {
  const { controller, cleanup } = createTimeoutController();

  try {
    const response = await fetch(`${API_BASE_URL}/api/super-admin/tenants/${tenantId}/stripe/sync`, {
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
