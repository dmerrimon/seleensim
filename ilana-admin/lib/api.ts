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
 * Validate current user's session
 */
export async function validateSession(options: ApiOptions): Promise<{
  status: string;
  user: { id: string; email: string; name: string; is_admin: boolean } | null;
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
