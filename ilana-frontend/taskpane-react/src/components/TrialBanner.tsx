import { Clock, ExternalLink } from 'lucide-react';

interface TrialBannerProps {
  daysRemaining: number;
  isExpired: boolean;
  pricingUrl?: string;
}

export function TrialBanner({ daysRemaining, isExpired, pricingUrl = 'https://ilanaimmersive.com/pricing' }: TrialBannerProps) {
  if (isExpired) {
    return (
      <div className="bg-red-50 border-b border-red-200 px-3 py-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-red-500" />
            <span className="text-sm font-medium text-red-700">
              Trial expired
            </span>
          </div>
          <a
            href={pricingUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs font-medium text-red-600 hover:text-red-800"
          >
            Subscribe now
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>
    );
  }

  // Show banner for last 7 days of trial
  if (daysRemaining > 7) {
    return null;
  }

  const urgency = daysRemaining <= 3 ? 'high' : 'medium';
  const bgColor = urgency === 'high' ? 'bg-amber-50' : 'bg-gray-50';
  const borderColor = urgency === 'high' ? 'border-amber-200' : 'border-gray-200';
  const textColor = urgency === 'high' ? 'text-amber-700' : 'text-gray-600';
  const iconColor = urgency === 'high' ? 'text-amber-500' : 'text-gray-400';
  const linkColor = urgency === 'high' ? 'text-amber-600 hover:text-amber-800' : 'text-gray-500 hover:text-gray-700';

  return (
    <div className={`${bgColor} border-b ${borderColor} px-3 py-2`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className={`h-4 w-4 ${iconColor}`} />
          <span className={`text-sm font-medium ${textColor}`}>
            {daysRemaining} day{daysRemaining !== 1 ? 's' : ''} left in trial
          </span>
        </div>
        <a
          href={pricingUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={`flex items-center gap-1 text-xs font-medium ${linkColor}`}
        >
          View plans
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );
}
