import { Lock, CreditCard, FileText, Calendar, Check, Building2, GraduationCap } from 'lucide-react';

interface UsageStats {
  protocolsAnalyzed: number;
  issuesCaught: number;
}

interface PricingInfo {
  detectedPlan: 'corporate' | 'enterprise';
  orgType?: string;
}

interface TrialExpiredPaywallProps {
  isOpen: boolean;
  usageStats?: UsageStats;
  pricingInfo?: PricingInfo;
  orgName?: string;
  subscribeUrl?: string;
  onRequestInvoice?: () => void;
  onScheduleDemo?: () => void;
}

export function TrialExpiredPaywall({
  isOpen,
  usageStats = { protocolsAnalyzed: 0, issuesCaught: 0 },
  pricingInfo = { detectedPlan: 'enterprise' },
  orgName,
  subscribeUrl = 'https://admin.ilanaimmersive.com/subscribe',
  onRequestInvoice,
  onScheduleDemo,
}: TrialExpiredPaywallProps) {
  if (!isOpen) return null;

  const isCorporate = pricingInfo.detectedPlan === 'corporate';
  const qualifiesForCorporate = isCorporate ||
    ['university', 'nonprofit'].includes(pricingInfo.orgType || '');

  const handleSubscribe = () => {
    const params = new URLSearchParams({
      plan: pricingInfo.detectedPlan,
      ...(orgName && { org: orgName }),
    });
    window.open(`${subscribeUrl}?${params.toString()}`, '_blank');
  };

  const handleRequestInvoice = () => {
    if (onRequestInvoice) {
      onRequestInvoice();
    } else {
      const params = new URLSearchParams({
        plan: pricingInfo.detectedPlan,
        invoice: 'true',
        ...(orgName && { org: orgName }),
      });
      window.open(`${subscribeUrl}?${params.toString()}`, '_blank');
    }
  };

  const handleScheduleDemo = () => {
    if (onScheduleDemo) {
      onScheduleDemo();
    } else {
      window.open('https://calendly.com/ilana-demo/30min', '_blank');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-60">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-gray-800 to-gray-900 px-6 py-5 text-center">
          <div className="mx-auto w-14 h-14 rounded-full bg-white/10 flex items-center justify-center mb-3">
            <Lock className="h-7 w-7 text-white" />
          </div>
          <h2 className="text-xl font-semibold text-white">
            Your 14-day trial has ended
          </h2>
        </div>

        {/* Usage Stats */}
        {(usageStats.protocolsAnalyzed > 0 || usageStats.issuesCaught > 0) && (
          <div className="bg-emerald-50 px-6 py-4 border-b border-emerald-100">
            <p className="text-sm text-emerald-800 text-center">
              Your team analyzed{' '}
              <span className="font-bold">{usageStats.protocolsAnalyzed}</span> protocols
              and caught{' '}
              <span className="font-bold">{usageStats.issuesCaught}</span> compliance issues.
            </p>
          </div>
        )}

        {/* Pricing Options */}
        <div className="px-6 py-5 space-y-4">
          <p className="text-sm text-gray-600 text-center mb-4">
            Choose your plan to continue:
          </p>

          {/* Corporate Plan (if qualified) */}
          {qualifiesForCorporate && (
            <div className="border-2 border-emerald-500 rounded-lg p-4 bg-emerald-50/50">
              <div className="flex items-center gap-2 mb-2">
                <GraduationCap className="h-5 w-5 text-emerald-600" />
                <span className="text-sm font-medium text-emerald-700">
                  Your organization qualifies for Corporate pricing
                </span>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-bold text-gray-900">$75</span>
                <span className="text-gray-600">/user/month</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                For universities & non-profits
              </p>
            </div>
          )}

          {/* Divider */}
          {qualifiesForCorporate && (
            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-gray-200" />
              <span className="text-xs text-gray-400 font-medium">OR</span>
              <div className="flex-1 h-px bg-gray-200" />
            </div>
          )}

          {/* Enterprise Plan */}
          <div className={`border rounded-lg p-4 ${!qualifiesForCorporate ? 'border-blue-500 bg-blue-50/50' : 'border-gray-200'}`}>
            <div className="flex items-center gap-2 mb-2">
              <Building2 className="h-5 w-5 text-blue-600" />
              <span className="text-sm font-medium text-gray-700">
                Enterprise Plan
              </span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold text-gray-900">$149</span>
              <span className="text-gray-600">/user/month</span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              For pharma, CRO, and biotech companies
            </p>
            <div className="mt-3 space-y-1">
              <div className="flex items-center gap-2 text-xs text-gray-600">
                <Check className="h-3.5 w-3.5 text-emerald-500" />
                <span>Unlimited protocol analysis</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-600">
                <Check className="h-3.5 w-3.5 text-emerald-500" />
                <span>FDA & ICH-GCP compliance</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-600">
                <Check className="h-3.5 w-3.5 text-emerald-500" />
                <span>Team collaboration</span>
              </div>
            </div>
          </div>
        </div>

        {/* CTAs */}
        <div className="px-6 pb-5 space-y-3">
          <button
            onClick={handleSubscribe}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 transition-colors"
          >
            <CreditCard className="h-4 w-4" />
            Subscribe with Card
          </button>

          <div className="flex gap-3">
            <button
              onClick={handleRequestInvoice}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors text-sm"
            >
              <FileText className="h-4 w-4" />
              Request Invoice
            </button>
            <button
              onClick={handleScheduleDemo}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors text-sm"
            >
              <Calendar className="h-4 w-4" />
              Schedule Demo
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-3 text-center border-t border-gray-100">
          <p className="text-xs text-gray-500">
            Questions?{' '}
            <a
              href="mailto:sales@ilanaimmersive.com"
              className="text-emerald-600 hover:underline"
            >
              Contact sales
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
