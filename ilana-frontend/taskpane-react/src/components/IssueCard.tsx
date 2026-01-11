import { BookOpen, ChevronDown, ChevronRight, Check, X } from 'lucide-react';
import type { Issue } from '../types';
import { SEVERITY_CONFIG } from '../types';

interface IssueCardProps {
  issue: Issue;
  isExpanded: boolean;
  isActive: boolean;
  onToggle: () => void;
  onLocate: () => void;
  onAccept: () => void;
  onDismiss: () => void;
  onRemove: () => void;
  isAccepting?: boolean;
}

export function IssueCard({
  issue,
  isExpanded,
  isActive,
  onToggle,
  onLocate,
  onAccept,
  onDismiss,
  onRemove,
  isAccepting = false,
}: IssueCardProps) {
  const severityConfig = SEVERITY_CONFIG[issue.severity];

  // Truncate text for collapsed view
  const truncate = (text: string, maxLen: number) =>
    text.length > maxLen ? text.slice(0, maxLen) + '...' : text;

  // Get display text (handle both API formats)
  const originalText = issue.highlighted_text || issue.original || '';
  const suggestedText = issue.suggested_text || issue.suggested || '';

  return (
    <div
      className={`rounded-lg border transition-all ${
        isActive
          ? 'border-blue-400 bg-blue-50/50 ring-2 ring-blue-400/30'
          : isExpanded
            ? 'border-gray-300 bg-white shadow-sm'
            : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
      }`}
    >
      {/* Clickable Header - Always visible */}
      <div className="p-3">
        <div className="flex items-start gap-2">
          {/* Severity Dot */}
          <div className={`mt-1 h-2.5 w-2.5 rounded-full flex-shrink-0 ${severityConfig.dotColor}`} />

          {/* Main content - clickable for expand/collapse */}
          <button
            onClick={onToggle}
            className="flex-1 min-w-0 text-left focus:outline-none"
          >
            {/* Top row: expand icon */}
            <div className="flex items-center justify-end mb-1.5">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-gray-400" />
              ) : (
                <ChevronRight className="h-4 w-4 text-gray-400" />
              )}
            </div>

            {/* Text diff preview - always shown */}
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="text-red-600 line-through">
                {truncate(originalText, isExpanded ? 80 : 25)}
              </span>
              <span className="text-gray-400">→</span>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  onLocate();
                }}
                className="inline-flex items-center px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 hover:bg-green-200 cursor-pointer transition-colors"
              >
                {truncate(suggestedText, isExpanded ? 80 : 25)}
              </span>
            </div>
          </button>

          {/* Close button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            className="p-1 hover:bg-gray-100 rounded-md transition-colors flex-shrink-0 self-start"
            aria-label="Remove suggestion"
            title="Remove this suggestion"
          >
            <X className="w-4 h-4 text-gray-500 hover:text-gray-700" />
          </button>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-3 pb-3 pt-0 ml-5">
          {/* Severity + Title */}
          <div className="mb-2">
            <span className={`text-xs font-semibold uppercase ${severityConfig.color}`}>
              {severityConfig.label}
            </span>
            <h4 className="font-medium text-gray-900 text-sm mt-0.5">
              {issue.title}
            </h4>
          </div>

          {/* Original Text */}
          <div className="mb-2">
            <label className="block text-xs font-medium text-gray-500 mb-0.5">Original</label>
            <p className="text-xs text-red-700 bg-red-50 px-2 py-1.5 rounded line-through">
              {originalText}
            </p>
          </div>

          {/* Suggested Text */}
          <div className="mb-2">
            <label className="block text-xs font-medium text-gray-500 mb-0.5">Suggested</label>
            <button
              onClick={onLocate}
              className="w-full text-left text-xs text-green-700 bg-green-50 px-2 py-1.5 rounded hover:bg-green-100 transition-colors"
            >
              {suggestedText}
              <span className="text-xs text-green-600 ml-1 opacity-70">(locate)</span>
            </button>
          </div>

          {/* Explanation */}
          <div className="mb-2">
            <label className="block text-xs font-medium text-gray-500 mb-0.5">Explanation</label>
            <p className="text-xs text-gray-700 leading-relaxed">
              {issue.explanation}
            </p>
          </div>

          {/* Clinical Impact (if present) */}
          {issue.clinical_impact && (
            <div className="mb-2">
              <label className="block text-xs font-medium text-gray-500 mb-0.5">Clinical Impact</label>
              <p className="text-xs text-gray-700 leading-relaxed bg-gray-50 px-2 py-1.5 rounded">
                {issue.clinical_impact}
              </p>
            </div>
          )}

          {/* Regulatory Reference */}
          {issue.regulatory_reference && (
            <div className="flex items-center text-xs text-blue-600 mb-3">
              <BookOpen className="h-3 w-3 mr-1" />
              {issue.regulatory_reference}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-2 mt-3 pt-2 border-t border-gray-100">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onAccept();
              }}
              disabled={isAccepting}
              className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isAccepting ? (
                <span className="animate-spin h-3 w-3 border-2 border-white border-t-transparent rounded-full" />
              ) : (
                <>
                  <Check className="h-3 w-3" />
                  Accept
                </>
              )}
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDismiss();
              }}
              className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-700 text-xs font-medium rounded hover:bg-gray-200 transition-colors"
            >
              <X className="h-3 w-3" />
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
