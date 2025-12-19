import type { AlignmentScores } from '../types';

interface AlignmentBadgesProps {
  scores: AlignmentScores;
  compact?: boolean;
}

function getScoreLevel(score: number): 'good' | 'warning' | 'danger' {
  if (score >= 75) return 'good';
  if (score >= 50) return 'warning';
  return 'danger';
}

const LEVEL_CONFIG = {
  good: {
    bg: 'bg-green-100',
    text: 'text-green-700',
    icon: '✓',
  },
  warning: {
    bg: 'bg-yellow-100',
    text: 'text-yellow-700',
    icon: '⚠',
  },
  danger: {
    bg: 'bg-red-100',
    text: 'text-red-700',
    icon: '✗',
  },
};

const LABEL_MAP = {
  compliance: 'Comp',
  clarity: 'Clar',
  feasibility: 'Feas',
};

export function AlignmentBadges({ scores, compact = false }: AlignmentBadgesProps) {
  const metrics = [
    { key: 'compliance' as const, score: scores.compliance },
    { key: 'clarity' as const, score: scores.clarity },
    { key: 'feasibility' as const, score: scores.feasibility },
  ];

  return (
    <div className="flex items-center gap-1.5">
      {metrics.map(({ key, score }) => {
        const level = getScoreLevel(score);
        const config = LEVEL_CONFIG[level];

        return (
          <div
            key={key}
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}
            title={`${key.charAt(0).toUpperCase() + key.slice(1)}: ${score}/100`}
          >
            <span>{config.icon}</span>
            <span>{LABEL_MAP[key]}</span>
            {!compact && <span className="opacity-70">{score}</span>}
          </div>
        );
      })}
    </div>
  );
}
