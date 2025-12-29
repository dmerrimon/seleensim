import type { Issue, AnalysisResponse } from '../types';

// Trial status response from API
export interface TrialStatus {
  is_trial: boolean;
  days_remaining: number | null;
  status: 'active' | 'expired' | 'grace';
  is_blocked: boolean;
}

// Subscription info including plan tier
export interface SubscriptionInfo {
  plan_type: string;  // trial, active, expired
  plan_tier: 'individual' | 'team' | 'team_plus';
  seats_used: number;
  seats_total: number;
}

// API Base URL - can be overridden via window config
const getApiBaseUrl = (): string => {
  // Check for runtime config
  if (typeof window !== 'undefined' && (window as any).__ILANA_API_BASE__) {
    return (window as any).__ILANA_API_BASE__;
  }
  // Default to production
  return 'https://ilanalabs-add-in.onrender.com';
};

// Normalize issue from API response
export function normalizeIssue(rawIssue: any, index: number): Issue {
  // Get the full original text (sentence/paragraph context)
  const fullOriginalText = rawIssue.text || rawIssue.original || rawIssue.highlighted_text || '';

  // Get the problematic text for word-level highlighting (just the problematic words)
  // This is what we use for locating/highlighting in the document
  const problematicText = rawIssue.problematic_text || fullOriginalText;

  return {
    id: rawIssue.id || `issue_${index}`,
    // highlighted_text is used for document highlighting - use problematic_text for word-level precision
    highlighted_text: problematicText,
    // original stores the full sentence context for display
    original: fullOriginalText,
    // problematic_text explicitly stored for clarity
    problematic_text: problematicText,
    suggested_text: rawIssue.suggested || rawIssue.suggested_text || rawIssue.improved_text || '',
    suggested: rawIssue.suggested || rawIssue.suggested_text || rawIssue.improved_text || '',
    category: rawIssue.category || 'clarity',
    severity: rawIssue.severity || 'minor',
    title: rawIssue.title || 'Suggestion',
    explanation: rawIssue.explanation || rawIssue.rationale || '',
    regulatory_reference: rawIssue.regulatory_reference || rawIssue.ref || null,
    clinical_impact: rawIssue.clinical_impact || rawIssue.clinicalImpact || '',
    alignment_scores: rawIssue.alignment_scores || rawIssue.alignmentScores || {
      compliance: rawIssue.complianceScore || 70,
      clarity: rawIssue.clarityScore || 70,
      feasibility: rawIssue.feasibilityScore || 70,
    },
    status: 'pending',
  };
}

// Analyze text via API
export async function analyzeText(
  text: string,
  therapeuticArea?: string,
  documentContext?: string
): Promise<Issue[]> {
  const apiUrl = getApiBaseUrl();

  try {
    const payload: Record<string, string | undefined> = {
      text,
      therapeutic_area: therapeuticArea,
    };

    // Include document context if provided (for better suggestions)
    if (documentContext) {
      payload.document_context = documentContext;
    }

    const response = await fetch(`${apiUrl}/api/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const data: AnalysisResponse = await response.json();
    const suggestions = data.suggestions || data as any;

    // Handle both array and object responses
    const issueArray = Array.isArray(suggestions) ? suggestions : [suggestions];

    return issueArray.map((issue, index) => normalizeIssue(issue, index));
  } catch (error) {
    console.error('Analysis API error:', error);
    throw error;
  }
}

// Send feedback to API
export async function sendFeedback(
  issueId: string,
  action: 'accepted' | 'dismissed',
  originalText: string,
  suggestedText: string
): Promise<void> {
  const apiUrl = getApiBaseUrl();

  try {
    await fetch(`${apiUrl}/api/rl-feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        suggestion_id: issueId,
        action,
        original: originalText,
        suggested: suggestedText,
      }),
    });
  } catch (error) {
    console.error('Feedback API error:', error);
    // Don't throw - feedback is non-critical
  }
}

// Fetch trial status from API
// Note: This requires authentication token from Azure AD
export async function fetchTrialStatus(token?: string): Promise<TrialStatus> {
  const apiUrl = getApiBaseUrl();

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${apiUrl}/api/subscription/status`, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      // If unauthorized or error, assume trial expired
      if (response.status === 401 || response.status === 403) {
        return {
          is_trial: false,
          days_remaining: null,
          status: 'expired',
          is_blocked: true,
        };
      }
      throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();
    return {
      is_trial: data.is_trial ?? true,
      days_remaining: data.days_remaining ?? null,
      status: data.status ?? 'active',
      is_blocked: data.is_blocked ?? false,
    };
  } catch (error) {
    console.error('Trial status API error:', error);
    // Default to active trial to avoid blocking users on API failure
    return {
      is_trial: true,
      days_remaining: 14,
      status: 'active',
      is_blocked: false,
    };
  }
}

// Fetch subscription info including plan tier
export async function fetchSubscriptionInfo(token: string): Promise<SubscriptionInfo | null> {
  const apiUrl = getApiBaseUrl();

  try {
    const response = await fetch(`${apiUrl}/api/auth/me`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      console.error('Failed to fetch subscription info:', response.status);
      return null;
    }

    const data = await response.json();

    if (data.tenant) {
      return {
        plan_type: data.tenant.plan_type || 'trial',
        plan_tier: data.tenant.plan_tier || 'individual',
        seats_used: data.tenant.seats_used || 0,
        seats_total: data.tenant.seats_total || 1,
      };
    }

    return null;
  } catch (error) {
    console.error('Subscription info API error:', error);
    return null;
  }
}

// Open Stripe Customer Portal (for Individual plan users only)
export async function openBillingPortal(token: string): Promise<boolean> {
  const apiUrl = getApiBaseUrl();

  try {
    const response = await fetch(`${apiUrl}/api/billing/portal`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      console.error('Billing portal error:', error.detail || response.status);
      return false;
    }

    const data = await response.json();

    if (data.url) {
      // Open in new tab
      window.open(data.url, '_blank');
      return true;
    }

    return false;
  } catch (error) {
    console.error('Billing portal API error:', error);
    return false;
  }
}
