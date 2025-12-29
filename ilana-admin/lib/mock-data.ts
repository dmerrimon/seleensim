/**
 * Mock data for development mode
 * Allows testing the admin portal UI without Microsoft SSO
 */

import { DashboardData, BillingStatus, ConversionInfo } from './api';

export const mockDashboardData: DashboardData = {
  tenant: {
    id: "dev-tenant-123",
    name: "Dev Test Organization"
  },
  subscription: {
    plan_type: "trial",
    seats_total: 10,
    seats_used: 4,
    seats_available: 6
  },
  users: [
    {
      id: "user-1",
      email: "admin@testcompany.com",
      display_name: "Sarah Johnson (Admin)",
      is_admin: true,
      has_seat: true,
      seat_assigned_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      last_active_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString()
    },
    {
      id: "user-2",
      email: "mike.chen@testcompany.com",
      display_name: "Mike Chen",
      is_admin: false,
      has_seat: true,
      seat_assigned_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
      last_active_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString()
    },
    {
      id: "user-3",
      email: "emily.watson@testcompany.com",
      display_name: "Emily Watson",
      is_admin: false,
      has_seat: true,
      seat_assigned_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
      last_active_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString()
    },
    {
      id: "user-4",
      email: "james.miller@testcompany.com",
      display_name: "James Miller",
      is_admin: false,
      has_seat: true,
      seat_assigned_at: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
      last_active_at: new Date(Date.now() - 35 * 24 * 60 * 60 * 1000).toISOString() // Inactive
    },
    {
      id: "user-5",
      email: "lisa.park@testcompany.com",
      display_name: "Lisa Park",
      is_admin: false,
      has_seat: false,
      seat_assigned_at: null,
      last_active_at: null
    }
  ],
  stats: {
    total_users: 5,
    users_with_seats: 4,
    inactive_users: 1,
    inactive_threshold_days: 30
  },
  trial: {
    status: "trial",
    is_trial: true,
    days_remaining: 10,
    grace_days_remaining: null,
    ends_at: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
    message: "10 days remaining in your free trial"
  }
};

// Alternative mock data scenarios for testing different states
export const mockExpiredTrial: DashboardData = {
  ...mockDashboardData,
  trial: {
    status: "expired",
    is_trial: true,
    days_remaining: 0,
    grace_days_remaining: 5,
    ends_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    message: "Trial expired - 5 days grace period remaining"
  }
};

export const mockActiveSubscription: DashboardData = {
  ...mockDashboardData,
  subscription: {
    plan_type: "professional",
    seats_total: 25,
    seats_used: 12,
    seats_available: 13
  },
  trial: {
    status: "active",
    is_trial: false,
    days_remaining: null,
    message: "Active subscription"
  }
};

export const isDevMode = (): boolean => {
  return process.env.NEXT_PUBLIC_DEV_MODE === 'true';
};

// Mock super admin status (set to true to test super admin features)
export const mockIsSuperAdmin = true;

// Mock billing status data
export const mockBillingStatus: BillingStatus = {
  status: 'trial',
  plan_type: 'trial',
  seats_used: 4,
  seats_total: 10,
  is_trial: true,
  trial_days_remaining: 10,
  trial_ends_at: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
  has_stripe_subscription: false,
  next_billing_date: null,
  billing_interval: null,
  contact_email: 'sales@ilanaimmersive.com',
  message: 'Trial: 10 days remaining',
};

export const mockActiveBillingStatus: BillingStatus = {
  status: 'active',
  plan_type: 'active',
  seats_used: 12,
  seats_total: 25,
  is_trial: false,
  trial_days_remaining: null,
  trial_ends_at: null,
  has_stripe_subscription: true,
  next_billing_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
  billing_interval: 'month',
  contact_email: 'sales@ilanaimmersive.com',
  message: null,
};

// Mock conversion info for B2B trial-to-paid conversion (Enterprise - no discount)
export const mockConversionInfo: ConversionInfo = {
  plan: 'enterprise',
  plan_label: 'Enterprise',
  seats: 10,
  pricing: {
    monthly_per_seat: 149,
    annual_per_seat: 1490,
    monthly_total: 1490,
    annual_total: 14900,
    annual_savings: 2980,  // 2 months free on annual
  },
  trial_status: {
    is_trial: true,
    days_remaining: 3,
    trial_ends_at: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
    is_expired: false,
  },
  // No discount - commercial org
  email_domain: 'pfizer.com',
  org_type: 'pharmaceutical',
  is_discount_applied: false,
  is_verified: false,
  needs_review: false,
};

// Mock for expired trial scenario (Corporate with .edu discount)
export const mockExpiredConversionInfo: ConversionInfo = {
  plan: 'corporate',
  plan_label: 'Corporate',
  seats: 5,
  pricing: {
    monthly_per_seat: 75,
    annual_per_seat: 750,
    monthly_total: 375,
    annual_total: 3750,
    annual_savings: 750,
  },
  trial_status: {
    is_trial: true,
    days_remaining: 0,
    trial_ends_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    is_expired: true,
  },
  // .edu discount applied
  email_domain: 'hms.harvard.edu',
  org_type: 'university',
  is_discount_applied: true,
  is_verified: true,
  needs_review: false,
  discount_reason: 'Educational institution (.edu domain)',
};

// Mock for university with discount (for testing discount banner)
export const mockUniversityConversionInfo: ConversionInfo = {
  plan: 'corporate',
  plan_label: 'Corporate',
  seats: 10,
  pricing: {
    monthly_per_seat: 75,
    annual_per_seat: 750,
    monthly_total: 750,
    annual_total: 7500,
    annual_savings: 1500,
  },
  trial_status: {
    is_trial: true,
    days_remaining: 10,
    trial_ends_at: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
    is_expired: false,
  },
  // .edu discount applied
  email_domain: 'stanford.edu',
  org_type: 'university',
  is_discount_applied: true,
  is_verified: false,
  needs_review: false,
  discount_reason: 'Educational institution (.edu domain)',
};
