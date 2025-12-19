import type { FilterState, IssueCategory, IssueSeverity } from '../types';

interface IssueFilterProps {
  filter: FilterState;
  onFilterChange: (filter: FilterState) => void;
  availableCategories: IssueCategory[];
  availableSeverities: IssueSeverity[];
}

const CATEGORY_LABELS: Record<IssueCategory | 'all', string> = {
  all: 'All Categories',
  compliance: 'Compliance',
  clarity: 'Clarity',
  terminology: 'Terminology',
  risk: 'Risk',
};

const SEVERITY_LABELS: Record<IssueSeverity | 'all', string> = {
  all: 'All Severities',
  critical: 'Critical',
  major: 'Major',
  minor: 'Minor',
  advisory: 'Advisory',
};

export function IssueFilter({
  filter,
  onFilterChange,
  availableCategories,
  availableSeverities,
}: IssueFilterProps) {
  return (
    <div className="flex gap-2">
      <select
        value={filter.category}
        onChange={(e) => onFilterChange({ ...filter, category: e.target.value as IssueCategory | 'all' })}
        className="flex-1 text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-400"
      >
        <option value="all">{CATEGORY_LABELS.all}</option>
        {availableCategories.map((cat) => (
          <option key={cat} value={cat}>{CATEGORY_LABELS[cat]}</option>
        ))}
      </select>

      <select
        value={filter.severity}
        onChange={(e) => onFilterChange({ ...filter, severity: e.target.value as IssueSeverity | 'all' })}
        className="flex-1 text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-400"
      >
        <option value="all">{SEVERITY_LABELS.all}</option>
        {availableSeverities.map((sev) => (
          <option key={sev} value={sev}>{SEVERITY_LABELS[sev]}</option>
        ))}
      </select>
    </div>
  );
}
