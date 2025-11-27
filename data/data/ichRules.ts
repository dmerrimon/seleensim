import { ICHComplianceRule } from '../types/analysis';

export const ICHComplianceRules: ICHComplianceRule[] = [
  {
    id: 'ICH-E6-2.1',
    section: '2.1',
    title: 'Protocol must specify objectives',
    description: 'The protocol should clearly state the objectives and purpose of the trial.',
    category: 'protocol_design',
    severity: 'critical',
    keywords: ['objective', 'purpose', 'aim', 'goal'],
    patterns: [
      /objective.*not.*defined/gi,
      /purpose.*unclear/gi,
      /aim.*missing/gi
    ]
  },
  {
    id: 'ICH-E6-2.2',
    section: '2.2',
    title: 'Background and rationale required',
    description: 'Protocol must include background information and scientific rationale.',
    category: 'protocol_design',
    severity: 'critical',
    keywords: ['background', 'rationale', 'justification'],
    patterns: [
      /background.*insufficient/gi,
      /rationale.*missing/gi,
      /justification.*inadequate/gi
    ]
  },
  {
    id: 'ICH-E6-4.1',
    section: '4.1',
    title: 'Investigator qualifications',
    description: 'Investigators must be qualified by education, training, and experience.',
    category: 'ethics',
    severity: 'critical',
    keywords: ['investigator', 'qualification', 'training', 'experience'],
    patterns: [
      /investigator.*unqualified/gi,
      /training.*incomplete/gi,
      /experience.*insufficient/gi
    ]
  },
  {
    id: 'ICH-E6-4.8',
    section: '4.8',
    title: 'Informed consent process',
    description: 'Subjects must provide informed consent before any trial-related procedures.',
    category: 'ethics',
    severity: 'critical',
    keywords: ['informed consent', 'consent', 'agreement'],
    patterns: [
      /consent.*not.*obtained/gi,
      /informed.*consent.*missing/gi,
      /agreement.*absent/gi
    ]
  },
  {
    id: 'ICH-E6-5.1',
    section: '5.1',
    title: 'Data quality assurance',
    description: 'Quality assurance should be applied to each stage of data handling.',
    category: 'data_integrity',
    severity: 'major',
    keywords: ['data quality', 'quality assurance', 'data integrity'],
    patterns: [
      /data.*quality.*poor/gi,
      /quality.*assurance.*lacking/gi,
      /data.*integrity.*compromised/gi
    ]
  },
  {
    id: 'ICH-E6-5.5',
    section: '5.5',
    title: 'Source document requirements',
    description: 'Source documents must be attributable, legible, contemporaneous, original, and accurate.',
    category: 'documentation',
    severity: 'major',
    keywords: ['source document', 'documentation', 'record'],
    patterns: [
      /source.*document.*missing/gi,
      /documentation.*incomplete/gi,
      /record.*illegible/gi
    ]
  },
  {
    id: 'ICH-E6-6.4',
    section: '6.4',
    title: 'Protocol deviations',
    description: 'Protocol deviations should be documented and explained.',
    category: 'protocol_design',
    severity: 'major',
    keywords: ['deviation', 'protocol violation', 'non-compliance'],
    patterns: [
      /deviation.*undocumented/gi,
      /protocol.*violation.*unexplained/gi,
      /non.compliance.*unreported/gi
    ]
  },
  {
    id: 'ICH-E6-8.3',
    section: '8.3',
    title: 'Essential documents',
    description: 'Essential documents should be maintained to demonstrate compliance.',
    category: 'documentation',
    severity: 'major',
    keywords: ['essential document', 'documentation', 'compliance'],
    patterns: [
      /essential.*document.*missing/gi,
      /documentation.*insufficient/gi,
      /compliance.*record.*absent/gi
    ]
  },
  {
    id: 'CLARITY-001',
    section: 'General',
    title: 'Clear and concise language',
    description: 'Protocol language should be clear, concise, and unambiguous.',
    category: 'documentation',
    severity: 'minor',
    keywords: ['clarity', 'language', 'terminology'],
    patterns: [
      /ambiguous.*term/gi,
      /unclear.*definition/gi,
      /confusing.*language/gi
    ]
  },
  {
    id: 'SAFETY-001',
    section: 'Safety',
    title: 'Safety monitoring plan',
    description: 'Protocol must include adequate safety monitoring procedures.',
    category: 'safety',
    severity: 'critical',
    keywords: ['safety', 'monitoring', 'adverse event', 'SAE'],
    patterns: [
      /safety.*plan.*missing/gi,
      /monitoring.*inadequate/gi,
      /adverse.*event.*procedure.*unclear/gi
    ]
  },
  {
    id: 'STATS-001',
    section: 'Statistics',
    title: 'Statistical analysis plan',
    description: 'Statistical methods and analysis plan must be clearly described.',
    category: 'protocol_design',
    severity: 'major',
    keywords: ['statistical', 'analysis', 'sample size', 'power'],
    patterns: [
      /statistical.*method.*unclear/gi,
      /sample.*size.*not.*justified/gi,
      /power.*calculation.*missing/gi
    ]
  }
];