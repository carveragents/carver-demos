export const CER_SECTIONS = [
  {
    name: 'Clinical Background & State of the Art',
    status: 'ok',
    note: 'No changes needed',
    action: 'No action required at this time. Re-verify at next annual review.',
    effort: 'low',
  },
  {
    name: 'Equivalence Argument',
    status: 'critical',
    note: 'Predicate #1 recalled — equivalence claim needs reassessment',
    action: 'Draft a new equivalence assessment excluding CardioSense Pro. Identify alternative predicates or switch to a clinical investigation pathway if equivalence cannot be demonstrated. Consult with Notified Body.',
    effort: 'high',
  },
  {
    name: 'Clinical Data Appraisal',
    status: 'warning',
    note: '2 new relevant clinical studies identified since last update',
    action: 'Appraise and integrate 2 new RCTs on PPG-based AF detection in ambulatory cardiac monitoring. Assess their impact on the overall benefit-risk conclusion.',
    effort: 'medium',
  },
  {
    name: 'Post-Market Clinical Data',
    status: 'critical',
    note: 'AE signal spike on Predicate #2 requires new comparative analysis',
    action: "Add a comparative MAUDE analysis section covering VitalTrack ECG's AE spike. Stratify by failure mode and document whether CardioWatch X1 shares the same algorithmic risk.",
    effort: 'high',
  },
  {
    name: 'PMCF Plan & Results',
    status: 'warning',
    note: 'MDCG 2026-3 requires plan amendments (quarterly cadence)',
    action: 'Amend PMCF plan to reflect quarterly submission cadence. Update endpoint definitions. Notify Notified Body of plan revision and obtain acknowledgement before Q4 2026.',
    effort: 'medium',
  },
  {
    name: 'Benefit-Risk Analysis',
    status: 'warning',
    note: 'Risk profile may shift given predicate device safety signals',
    action: 'Revisit the risk side of the benefit-risk balance with updated predicate safety data. Revise risk acceptability rationale under ISO 14971:2019 if necessary.',
    effort: 'medium',
  },
  {
    name: 'Literature Review',
    status: 'ok',
    note: 'Systematic search current — 3 minor additions flagged',
    action: 'Append 3 flagged papers as minor additions to the literature matrix. No structural revision required.',
    effort: 'low',
  },
  {
    name: 'Standards Compliance',
    status: 'warning',
    note: 'IEC 62304:2026 amendment — gap analysis needed',
    action: 'Commission a gap analysis between current IEC 62304:2015 compliance posture and 2026 amendment requirements. Document findings and initiate remediation plan.',
    effort: 'medium',
  },
]

export const HORIZON_ITEMS = [
  {
    type: 'STANDARD',
    tagClass: 'tag-blue',
    title: 'IEC 62304:2026 Amendment — Cybersecurity Integration',
    timeline: 'Effective Sep 2027',
    impact: "Mandatory cybersecurity risk assessment in SDLC. Your device's Class B software classification may change under new criteria. 18-month transition.",
    detail: "CardioWatch X1's adaptive AF algorithm may be reclassified as Class C software under the new criteria, triggering additional documentation and testing requirements. Recommend initiating gap analysis now to avoid a compressed remediation timeline.",
    steps: [
      'Engage software team for preliminary gap analysis (Q2 2026)',
      'Map current SDLC activities to IEC 62304:2026 annex requirements',
      'Update technical file with revised software classification rationale',
    ],
  },
  {
    type: 'REGULATION',
    tagClass: 'tag-amber',
    title: 'EU MDR MDCG 2026-3 — Quarterly PMCF for Cardiac IIb',
    timeline: 'Q4 2026',
    impact: 'PMCF submission cadence changes from annual to quarterly. Plan amendments required. Notified Body notification needed.',
    detail: 'This directly affects CardioWatch X1 as a Class IIb cardiac monitoring device under EU MDR. The first quarterly submission under the new cadence would be due Q4 2026 — only months away. Failure to comply risks Certificate suspension.',
    steps: [
      'Amend PMCF plan document immediately',
      'Notify Notified Body of plan revision (required before first quarterly submission)',
      'Set up quarterly data extraction pipeline from PMCF registry',
    ],
  },
  {
    type: 'TRADE',
    tagClass: 'tag-purple',
    title: 'India HS Code Reclassification — Cardiovascular Monitors',
    timeline: 'Q3 2026 (proposed)',
    impact: 'Import duty increase from 7.5% to 15%. Comment period closes May 15. Coordinate regulatory + commercial response.',
    detail: 'CardioWatch X1 is marketed in India under HS code 9018.19. Reclassification to 9018.11 would double import duty, materially impacting India market margin. The May 15 comment window is an opportunity to push back via industry association.',
    steps: [
      'Alert commercial and finance teams by end of April',
      'File comment via AdvaMed India or FICCI by May 15',
      'Model pricing scenarios for 15% duty regime',
    ],
  },
  {
    type: 'GUIDANCE',
    tagClass: 'tag-green',
    title: 'FDA RWE Guidance for Cardiovascular Devices',
    timeline: 'Comment: Jul 2026',
    impact: 'Opportunity to strengthen PMCF study design using real-world evidence. Could improve next CER evidence quality.',
    detail: 'The draft guidance signals FDA acceptance of RWE from registries and EHR data for post-market cardiac device studies. Aligning your US PMCF study with this approach now positions CardioWatch X1 favorably for any future 510(k) supplements.',
    steps: [
      'Review draft guidance with clinical affairs team',
      'Submit comment if PMCF design is misaligned',
      'Consider amending US PMCF protocol to incorporate RWE endpoints',
    ],
  },
  {
    type: 'REGULATION',
    tagClass: 'tag-amber',
    title: 'UKCA Marking — Extended Transition Deadline',
    timeline: 'Jul 2027',
    impact: 'UK market access requires UKCA marking by new deadline. CE marking recognition ends. Plan conformity assessment with UK Approved Body.',
    detail: 'CE marking will no longer be recognised in Great Britain after July 2027. CardioWatch X1 must complete UKCA conformity assessment with a UK Approved Body. Given current Approved Body capacity constraints, 12–18 months lead time is typical.',
    steps: [
      'Identify and contract a UK Approved Body by Q3 2026',
      'Prepare UK-specific technical documentation package',
      'Plan UKCA certificate issuance before Jul 2027 deadline',
    ],
  },
  {
    type: 'STANDARD',
    tagClass: 'tag-blue',
    title: 'ISO 14971:2026 Revision — AI/ML Risk Management Annex',
    timeline: 'Draft expected Q1 2027',
    impact: 'New annex specifically addressing risk management for AI/ML-enabled medical devices. Early engagement recommended.',
    detail: "CardioWatch X1's adaptive algorithm could fall within scope of the new AI/ML annex. Early review of the draft will allow you to anticipate documentation changes before the standard is published and Notified Bodies begin expecting compliance.",
    steps: [
      'Track ISO TC 210 working group drafts via BSI or DIN membership',
      'Conduct internal workshop on AI/ML risk management gaps',
      'Plan ISO 14971 risk file update for 2027 CER cycle',
    ],
  },
]

export const HORIZON_QUARTERS = ['Q2 2026', 'Q3 2026', 'Q4 2026', 'Q1 2027', 'Q3 2027']

export const CER_STATS = [
  { label: 'Sections Need Update', value: '6/8', level: 'warning' },
  { label: 'Critical Issues',       value: '2',   level: 'critical' },
  { label: 'New Literature',        value: '5',   level: 'info' },
  { label: 'Predicate Changes',     value: '2',   level: 'critical' },
]

export const CER_PRIORITY = [
  { rank: 1, level: 'critical', text: "Reassess equivalence argument — Predicate #1 recall directly impacts your substantial equivalence claim." },
  { rank: 2, level: 'critical', text: "Update post-market clinical data section — Integrate Predicate #2 adverse event signal analysis." },
  { rank: 3, level: 'warning',  text: "Amend PMCF plan — New MDCG 2026-3 quarterly submission requirements." },
  { rank: 4, level: 'warning',  text: "Revise benefit-risk analysis — Incorporate updated predicate safety profiles." },
  { rank: 5, level: 'warning',  text: "IEC 62304 gap analysis — Begin early; 18-month transition but document readiness now." },
  { rank: 6, level: 'info',     text: "Literature review addendum — 3 minor additions, lowest effort." },
]
