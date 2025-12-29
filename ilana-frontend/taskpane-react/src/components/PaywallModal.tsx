import { Lock, ExternalLink, X } from 'lucide-react';

interface PaywallModalProps {
  isOpen: boolean;
  onClose?: () => void;
  pricingUrl?: string;
}

export function PaywallModal({
  isOpen,
  onClose,
  pricingUrl = 'https://ilanaimmersive.com/pricing'
}: PaywallModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl max-w-sm w-full mx-4 relative">
        {/* Close button - only show if onClose is provided */}
        {onClose && (
          <button
            onClick={onClose}
            className="absolute top-3 right-3 text-gray-400 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        )}

        {/* Content */}
        <div className="p-6 text-center">
          {/* Lock icon */}
          <div className="mx-auto w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-4">
            <Lock className="h-6 w-6 text-gray-500" />
          </div>

          {/* Title */}
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            Trial Period Ended
          </h2>

          {/* Description */}
          <p className="text-sm text-gray-600 mb-6">
            Your 14-day trial has expired. Subscribe to continue using ILANA
            Protocol Intelligence for clinical protocol analysis.
          </p>

          {/* Features list */}
          <div className="text-left mb-6 bg-gray-50 rounded-lg p-4">
            <p className="text-xs font-medium text-gray-700 mb-2">
              With a subscription, you get:
            </p>
            <ul className="text-xs text-gray-600 space-y-1">
              <li>- Unlimited protocol analysis</li>
              <li>- FDA & ICH-GCP guidance alignment</li>
              <li>- Real-time suggestions</li>
              <li>- Team collaboration tools</li>
            </ul>
          </div>

          {/* CTA Button */}
          <a
            href={pricingUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 transition-colors"
          >
            View Plans & Subscribe
            <ExternalLink className="h-4 w-4" />
          </a>

          {/* Contact link */}
          <p className="mt-4 text-xs text-gray-500">
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
