const MAX_CHARS = 15000;

interface HeaderProps {
  issueCount: number;
  isAnalyzing: boolean;
  onAnalyze: () => void;
  selectedCharCount: number;
  useDocumentContext: boolean;
  onToggleDocumentContext: () => void;
}

export function Header({
  issueCount,
  isAnalyzing,
  onAnalyze,
  selectedCharCount,
  useDocumentContext,
  onToggleDocumentContext
}: HeaderProps) {
  const isOverLimit = selectedCharCount > MAX_CHARS;

  return (
    <div className="bg-white border-b border-gray-200 px-4 py-3">
      {/* Issue count badge */}
      {issueCount > 0 && (
        <div className="flex justify-end mb-3">
          <div className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full text-xs font-medium">
            {issueCount} issue{issueCount !== 1 ? 's' : ''}
          </div>
        </div>
      )}

      {/* Document context toggle */}
      <label className="flex items-center gap-2 mb-3 cursor-pointer">
        <input
          type="checkbox"
          checked={useDocumentContext}
          onChange={onToggleDocumentContext}
          className="w-4 h-4 text-gray-900 bg-gray-100 border-gray-300 rounded focus:ring-gray-500 focus:ring-2"
        />
        <span className="text-xs text-gray-600">
          Include document context for better suggestions
        </span>
      </label>

      {/* Analyze Button */}
      <button
        onClick={onAnalyze}
        disabled={isAnalyzing || isOverLimit}
        className="w-full flex items-center justify-center gap-2 font-medium py-2 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
        style={{ backgroundColor: '#1e1e1e', color: '#ffffff' }}
      >
        {isAnalyzing ? (
          <>
            <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
            Analyzing...
          </>
        ) : (
          'Analyze Selection'
        )}
      </button>

      {/* Character counter - centered below button */}
      <div className="text-center mt-6">
        <span className={`${isOverLimit ? 'text-red-600' : 'text-gray-400'}`} style={{ fontSize: '11px' }}>
          {selectedCharCount.toLocaleString()} / {MAX_CHARS.toLocaleString()} chars
        </span>
        {isOverLimit && (
          <span className="text-red-500 ml-1" style={{ fontSize: '11px' }}>exceeded</span>
        )}
      </div>
    </div>
  );
}
