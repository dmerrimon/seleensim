/**
 * API Client for Ilana Backend
 *
 * Handles authenticated requests to the admin endpoints
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://ilanalabs-add-in.onrender.com';

interface ApiOptions {
  token: string;
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

export interface DashboardData {
  tenant: {
    id: string;
    name: string | null;
  };
  subscription: Subscription;
  users: User[];
  stats: Stats;
}

export interface SeatActionResult {
  success: boolean;
  seats_used?: number;
  seats_total?: number;
  user_email?: string;
  error?: string;
}

/**
 * Fetch dashboard data (user list + stats)
 */
export async function fetchDashboard(options: ApiOptions): Promise<DashboardData> {
  const response = await fetch(`${API_BASE_URL}/api/admin/users`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${options.token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Revoke a user's seat
 */
export async function revokeUserSeat(
  userId: string,
  options: ApiOptions
): Promise<SeatActionResult> {
  const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/revoke`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${options.token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Restore a user's seat
 */
export async function restoreUserSeat(
  userId: string,
  options: ApiOptions
): Promise<SeatActionResult> {
  const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/restore`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${options.token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Validate current user's session
 */
export async function validateSession(options: ApiOptions): Promise<{
  status: string;
  user: { id: string; email: string; name: string; is_admin: boolean } | null;
}> {
  const response = await fetch(`${API_BASE_URL}/api/auth/validate`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${options.token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}
