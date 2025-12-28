/**
 * Mock data for development mode
 * Allows testing the ops portal UI without Microsoft SSO
 */

import {
  SuperAdminStats,
  TenantSummary,
  TenantDetail,
  SuperAdminInfo,
} from './api';

export const isDevMode = (): boolean => {
  return process.env.NEXT_PUBLIC_DEV_MODE === 'true';
};

// Mock stats data
export const mockStats: SuperAdminStats = {
  total_tenants: 12,
  total_users: 156,
  active_subscriptions: 5,
  trials_active: 6,
  mrr: 2500.0,
};

// Mock tenants data
export const mockTenants: TenantSummary[] = [
  {
    id: '1',
    name: 'Pfizer Inc',
    azure_tenant_id: 'pfizer-azure-123',
    created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
    user_count: 45,
    seats_used: 42,
    seats_total: 50,
    subscription_status: 'active',
    trial_days_remaining: null,
    has_stripe_subscription: true,
  },
  {
    id: '2',
    name: 'Merck & Co',
    azure_tenant_id: 'merck-azure-456',
    created_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    user_count: 12,
    seats_used: 10,
    seats_total: 10,
    subscription_status: 'trial',
    trial_days_remaining: 8,
    has_stripe_subscription: false,
  },
  {
    id: '3',
    name: 'Test Organization',
    azure_tenant_id: 'test-azure-789',
    created_at: new Date(Date.now() - 20 * 24 * 60 * 60 * 1000).toISOString(),
    user_count: 2,
    seats_used: 1,
    seats_total: 5,
    subscription_status: 'expired',
    trial_days_remaining: -3,
    has_stripe_subscription: false,
  },
];

// Mock super admins
export const mockSuperAdmins: SuperAdminInfo[] = [
  {
    id: '1',
    email: 'dmerriman@ilanaimmersive.com',
    display_name: 'Don Merriman',
    tenant_id: 'tenant-1',
    tenant_name: 'Ilana Labs',
  },
];

// Mock tenant detail
export const mockTenantDetail: TenantDetail = {
  id: '1',
  name: 'Pfizer Inc',
  azure_tenant_id: 'pfizer-azure-123',
  created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
  subscription: {
    id: 'sub-1',
    plan_type: 'active',
    status: 'active',
    seats_total: 50,
    seats_used: 42,
    trial_started_at: null,
    trial_ends_at: null,
    trial_days_remaining: null,
    converted_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    stripe_customer_id: 'cus_mock123',
    stripe_subscription_id: 'sub_mock456',
    has_stripe: true,
  },
  users: [
    {
      id: 'user-1',
      email: 'admin@pfizer.com',
      display_name: 'John Admin',
      is_admin: true,
      has_seat: true,
      last_active_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
      created_at: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: 'user-2',
      email: 'sarah.researcher@pfizer.com',
      display_name: 'Sarah Researcher',
      is_admin: false,
      has_seat: true,
      last_active_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      created_at: new Date(Date.now() - 45 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: 'user-3',
      email: 'mike.scientist@pfizer.com',
      display_name: 'Mike Scientist',
      is_admin: false,
      has_seat: true,
      last_active_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
      created_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      id: 'user-4',
      email: 'jane.analyst@pfizer.com',
      display_name: 'Jane Analyst',
      is_admin: false,
      has_seat: false,
      last_active_at: null,
      created_at: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
    },
  ],
  audit_summary: {
    total_events: 1250,
    events_last_7_days: 87,
  },
};
