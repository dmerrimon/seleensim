import { useState, useMemo, useCallback, useEffect } from 'react';
import { AlertTriangle, FileText, CreditCard } from 'lucide-react';
import type { Issue, FilterState, IssueCategory, IssueSeverity } from '../types';
import { Header } from './Header';
import { IssueCard } from './IssueCard';
import { IssueFilter } from './IssueFilter';
import { TrialBanner } from './TrialBanner';
import { TrialExpiredPaywall } from './TrialExpiredPaywall';
import { useOffice } from '../hooks/useOffice';
import { useAuth } from '../hooks/useAuth';
import { analyzeText, sendFeedback, fetchTrialStatus, fetchSubscriptionInfo, openBillingPortal } from '../utils/api';
import type { TrialStatus, SubscriptionInfo } from '../utils/api';

export function Taskpane() {
  // Office integration
  const { isReady, isLoading: officeLoading, getSelectedText, getFullDocumentText, searchAndHighlight, replaceText } = useOffice();

  // Authentication
  const { token } = useAuth();

  // Subscription state
  const [subscriptionInfo, setSubscriptionInfo] = useState<SubscriptionInfo | null>(null);
  const [isOpeningBillingPortal, setIsOpeningBillingPortal] = useState(false);

  // State
  const [issues, setIssues] = useState<Issue[]>([]);
  const [expandedIssueId, setExpandedIssueId] = useState<string | null>(null);
  const [activeIssueId, setActiveIssueId] = useState<string | null>(null);
  const [acceptingIssueId, setAcceptingIssueId] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterState>({ category: 'all', severity: 'all' });
  const [selectedCharCount, setSelectedCharCount] = useState(0);
  const [useDocumentContext, setUseDocumentContext] = useState(false);

  // Trial state
  const [trialStatus, setTrialStatus] = useState<TrialStatus | null>(null);
  const [showPaywall, setShowPaywall] = useState(false);

  // Fetch trial status on mount
  useEffect(() => {
    const loadTrialStatus = async () => {
      try {
        const status = await fetchTrialStatus();
        setTrialStatus(status);
        // Show paywall if blocked
        if (status.is_blocked) {
          setShowPaywall(true);
        }
      } catch (error) {
        console.error('Failed to fetch trial status:', error);
      }
    };

    loadTrialStatus();
  }, []);

  // Fetch subscription info when token is available
  useEffect(() => {
    const loadSubscriptionInfo = async () => {
      if (!token) return;

      try {
        const info = await fetchSubscriptionInfo(token);
        setSubscriptionInfo(info);
      } catch (error) {
        console.error('Failed to fetch subscription info:', error);
      }
    };

    loadSubscriptionInfo();
  }, [token]);

  // Handler for opening billing portal
  const handleManageSubscription = useCallback(async () => {
    if (!token) return;

    setIsOpeningBillingPortal(true);
    try {
      const success = await openBillingPortal(token);
      if (!success) {
        console.error('Failed to open billing portal');
      }
    } catch (error) {
      console.error('Error opening billing portal:', error);
    } finally {
      setIsOpeningBillingPortal(false);
    }
  }, [token]);

  // Poll for selection changes to update character count
  useEffect(() => {
    if (!isReady) return;

    const updateCharCount = async () => {
      const text = await getSelectedText();
      setSelectedCharCount(text.length);
    };

    // Initial check
    updateCharCount();

    // Poll every 500ms for selection changes
    const interval = setInterval(updateCharCount, 500);

    return () => clearInterval(interval);
  }, [isReady, getSelectedText]);

  // Compute available categories and severities
  const availableCategories = useMemo(() => {
    const categories = new Set(issues.map((i) => i.category));
    return Array.from(categories) as IssueCategory[];
  }, [issues]);

  const availableSeverities = useMemo(() => {
    const severities = new Set(issues.map((i) => i.severity));
    return Array.from(severities) as IssueSeverity[];
  }, [issues]);

  // Filter issues
  const filteredIssues = useMemo(() => {
    return issues.filter((issue) => {
      if (issue.status === 'dismissed' || issue.status === 'accepted') return false;
      if (filter.category !== 'all' && issue.category !== filter.category) return false;
      if (filter.severity !== 'all' && issue.severity !== filter.severity) return false;
      return true;
    });
  }, [issues, filter]);

  // Handlers
  const handleAnalyze = useCallback(async () => {
    setIsAnalyzing(true);
    setAnalysisError(null);

    try {
      let selectedText = '';
      let documentContext = '';

      if (isReady) {
        selectedText = await getSelectedText();

        // Get full document context if enabled
        if (useDocumentContext) {
          documentContext = await getFullDocumentText();
        }
      }

      if (!selectedText) {
        setAnalysisError('Please select text in your document to analyze');
        setIsAnalyzing(false);
        return;
      }

      const newIssues = await analyzeText(selectedText, undefined, documentContext);
      setIssues(newIssues);

      if (newIssues.length === 0) {
        setAnalysisError('No issues found in the selected text');
      }
    } catch (err) {
      setAnalysisError('Failed to analyze text. Please try again.');
      console.error('Analysis error:', err);
    } finally {
      setIsAnalyzing(false);
    }
  }, [isReady, getSelectedText, getFullDocumentText, useDocumentContext]);

  const handleToggleDocumentContext = useCallback(() => {
    setUseDocumentContext((prev) => !prev);
  }, []);

  const handleToggle = useCallback((issueId: string) => {
    setExpandedIssueId((prev) => (prev === issueId ? null : issueId));
  }, []);

  const handleLocate = useCallback(async (issue: Issue) => {
    setActiveIssueId(issue.id);
    // Use problematic_text for word-level highlighting, fallback to highlighted_text or original
    const textToHighlight = issue.problematic_text || issue.highlighted_text || issue.original || '';
    if (isReady && textToHighlight) {
      await searchAndHighlight(textToHighlight);
    }
  }, [isReady, searchAndHighlight]);

  const handleAccept = useCallback(async (issue: Issue) => {
    const originalText = issue.highlighted_text || issue.original || '';
    const suggestedText = issue.suggested_text || issue.suggested || '';

    if (!originalText || !suggestedText) return;

    setAcceptingIssueId(issue.id);

    try {
      if (isReady) {
        const success = await replaceText(originalText, suggestedText);
        if (!success) {
          console.warn('Text not found in document');
        }
      }

      // Update issue status
      setIssues((prev) =>
        prev.map((i) => (i.id === issue.id ? { ...i, status: 'accepted' } : i))
      );

      // Send feedback
      sendFeedback(issue.id, 'accepted', originalText, suggestedText);

      // Collapse the card
      if (expandedIssueId === issue.id) {
        setExpandedIssueId(null);
      }
    } finally {
      setAcceptingIssueId(null);
    }
  }, [isReady, replaceText, expandedIssueId]);

  const handleDismiss = useCallback((issue: Issue) => {
    const originalText = issue.highlighted_text || issue.original || '';
    const suggestedText = issue.suggested_text || issue.suggested || '';

    // Update issue status
    setIssues((prev) =>
      prev.map((i) => (i.id === issue.id ? { ...i, status: 'dismissed' } : i))
    );

    // Send feedback
    sendFeedback(issue.id, 'dismissed', originalText, suggestedText);

    // Collapse the card
    if (expandedIssueId === issue.id) {
      setExpandedIssueId(null);
    }
  }, [expandedIssueId]);

  // Loading state
  if (officeLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto mb-2" />
          <p className="text-sm text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Determine if trial-related UI should show
  const isTrialActive = trialStatus?.is_trial && trialStatus?.status === 'active';
  const daysRemaining = trialStatus?.days_remaining ?? 14;

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Paywall Modal - blocks access when trial expired */}
      <TrialExpiredPaywall
        isOpen={showPaywall}
        usageStats={{
          protocolsAnalyzed: issues.length > 0 ? Math.max(1, Math.floor(issues.length / 3)) : 0,
          issuesCaught: issues.length,
        }}
        pricingInfo={{
          detectedPlan: subscriptionInfo?.plan_type === 'corporate' ? 'corporate' : 'enterprise',
          orgType: undefined,
        }}
        subscribeUrl="https://admin.ilanaimmersive.com/subscribe"
      />

      {/* Trial Banner - shows for trial users */}
      {isTrialActive && (
        <TrialBanner
          daysRemaining={daysRemaining}
          isExpired={false}
        />
      )}

      {/* Header with Analyze button */}
      <Header
        issueCount={filteredIssues.length}
        isAnalyzing={isAnalyzing}
        onAnalyze={handleAnalyze}
        selectedCharCount={selectedCharCount}
        useDocumentContext={useDocumentContext}
        onToggleDocumentContext={handleToggleDocumentContext}
      />

      {/* Main content */}
      <div className="flex-1 overflow-y-auto flex flex-col">
        {/* Error state - centered in taskpane */}
        {analysisError && (
          <div className="flex-1 flex items-center justify-center p-4">
            <div className="bg-gray-100 rounded-lg p-3 text-center">
              <AlertTriangle className="h-4 w-4 text-gray-500 mx-auto mb-2" />
              <p className="text-sm text-gray-600">{analysisError}</p>
            </div>
          </div>
        )}

        {/* Empty state - centered in taskpane */}
        {issues.length === 0 && !analysisError && (
          <div className="flex-1 flex items-center justify-center p-4">
            <div className="text-center">
              <FileText className="h-12 w-12 text-gray-300 mx-auto mb-3" />
              <h3 className="text-sm font-medium text-gray-900 mb-1">No analysis yet</h3>
              <p className="text-xs text-gray-500">
                Select text in your document and click "Analyze Selection" to get started
              </p>
            </div>
          </div>
        )}

        {/* Issues list */}
        {filteredIssues.length > 0 && (
          <div className="p-3">
            {/* Filter controls */}
            <div className="mb-3">
              <IssueFilter
                filter={filter}
                onFilterChange={setFilter}
                availableCategories={availableCategories}
                availableSeverities={availableSeverities}
              />
            </div>

            {/* Issue cards */}
            <div className="space-y-2">
              {filteredIssues.map((issue) => (
                <IssueCard
                  key={issue.id}
                  issue={issue}
                  isExpanded={expandedIssueId === issue.id}
                  isActive={activeIssueId === issue.id}
                  onToggle={() => handleToggle(issue.id)}
                  onLocate={() => handleLocate(issue)}
                  onAccept={() => handleAccept(issue)}
                  onDismiss={() => handleDismiss(issue)}
                  isAccepting={acceptingIssueId === issue.id}
                />
              ))}
            </div>
          </div>
        )}

        {/* Filtered empty state */}
        {issues.length > 0 && filteredIssues.length === 0 && !analysisError && (
          <div className="p-8 text-center">
            <AlertTriangle className="h-8 w-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">No issues match current filters</p>
          </div>
        )}
      </div>

      {/* Manage Subscription footer - only for Individual plan users */}
      {subscriptionInfo?.plan_tier === 'individual' && (
        <div className="border-t border-gray-200 p-3 bg-white">
          <button
            onClick={handleManageSubscription}
            disabled={isOpeningBillingPortal}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <CreditCard className="h-4 w-4" />
            {isOpeningBillingPortal ? 'Opening...' : 'Manage Subscription'}
          </button>
        </div>
      )}
    </div>
  );
}
