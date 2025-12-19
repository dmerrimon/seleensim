// Issue Types for Add-in
export type IssueCategory = 'compliance' | 'clarity' | 'terminology' | 'risk';
export type IssueSeverity = 'critical' | 'major' | 'minor' | 'advisory';

export interface AlignmentScores {
  compliance: number;  // 0-100
  clarity: number;     // 0-100
  feasibility: number; // 0-100
}

export interface Issue {
  id: string;
  paragraph_id?: string;
  start_offset?: number;
  end_offset?: number;
  highlighted_text: string;  // Text to highlight in document (usually problematic_text)
  original?: string;         // Full sentence/context from API
  problematic_text?: string; // Exact problematic phrase for word-level highlighting
  category: IssueCategory;
  severity: IssueSeverity;
  title: string;
  explanation: string;
  regulatory_reference: string | null;
  suggested_text: string;
  suggested?: string;        // Alias for suggested_text from API
  alignment_scores: AlignmentScores;
  clinical_impact?: string;
  // Add-in specific
  status?: 'pending' | 'accepted' | 'dismissed';
}

// UI State Types
export interface FilterState {
  category: IssueCategory | 'all';
  severity: IssueSeverity | 'all';
}

// API Response Types
export interface AnalysisResponse {
  suggestions: Issue[];
  metadata?: {
    total_issues: number;
    therapeutic_area?: string;
  };
}

// Severity styling helpers
export const SEVERITY_CONFIG: Record<IssueSeverity, { color: string; bgColor: string; dotColor: string; label: string }> = {
  critical: { color: 'text-red-700', bgColor: 'bg-red-100', dotColor: 'bg-red-500', label: 'Critical' },
  major: { color: 'text-orange-700', bgColor: 'bg-orange-100', dotColor: 'bg-orange-500', label: 'Major' },
  minor: { color: 'text-yellow-700', bgColor: 'bg-yellow-100', dotColor: 'bg-yellow-500', label: 'Minor' },
  advisory: { color: 'text-blue-700', bgColor: 'bg-blue-100', dotColor: 'bg-blue-500', label: 'Advisory' },
};

export const CATEGORY_CONFIG: Record<IssueCategory, { label: string; icon: string }> = {
  compliance: { label: 'Compliance', icon: 'shield' },
  clarity: { label: 'Clarity', icon: 'eye' },
  terminology: { label: 'Terminology', icon: 'book' },
  risk: { label: 'Risk', icon: 'alert-triangle' },
};

// Office.js type declarations
declare global {
  interface Window {
    Office?: typeof Office;
    Word?: typeof Word;
  }
}
