// Mock 510(k) Premarket Notification — CardioWatch X1
// 21 CFR Part 807 Subpart E · FDA K213456

export const K510_DOC = {
  meta: {
    k_number: 'K213456',
    submission_type: '510(k) Premarket Notification',
    decision: 'Substantially Equivalent',
    decision_date: 'November 4, 2021',
    applicant: 'CardioTech Diagnostics Inc.',
    applicant_address: '3301 Harbor Boulevard, Suite 220, Santa Clara, CA 95054',
    contact: 'Dr. Sarah Kim, VP Regulatory Affairs',
    device_name: 'CardioWatch X1',
    trade_name: 'CardioWatch X1 Ambulatory Cardiac Monitor',
    product_code: 'DSI',
    regulation_number: '21 CFR 870.2900',
    device_class: 'II',
    panel: 'Cardiovascular',
    classification_name: 'Electrocardiograph',
    cleared_date: 'November 4, 2021',
  },

  device_description: {
    summary: 'The CardioWatch X1 is a wearable, patch-type ambulatory cardiac monitor intended for continuous ECG and photoplethysmographic (PPG) recording in adult patients over monitoring periods of up to 14 days. The device combines single-lead ECG acquisition with PPG-based pulse oximetry and employs a proprietary adaptive algorithm (CardioSense AF-Detect v2.1) for real-time atrial fibrillation (AF) detection and alerting.',
    technology: [
      'Single-lead dry-electrode ECG (Lead I equivalent, sample rate 250 Hz)',
      'Reflective PPG with dual-wavelength photodiodes (660 nm / 940 nm)',
      'Adaptive AF detection algorithm — CardioSense AF-Detect v2.1 (IEC 62304 Class B)',
      'Bluetooth Low Energy 5.2 for wireless data transfer to companion app',
      'Rechargeable Li-Po cell (36 mAh), up to 14 days continuous monitoring',
      'Hypoallergenic medical-grade silicone housing + conductive hydrogel electrodes',
      'IP67 dust and water resistance',
    ],
    dimensions: '52mm × 38mm × 8.5mm, weight 14g',
    materials: ['Medical-grade silicone (ISO 10993-5 biocompatibility tested)', 'Conductive hydrogel electrodes (latex-free)', 'Stainless steel electrical contacts'],
    software_version: 'Firmware v2.1.4 · App v3.0.2 (iOS 14+ / Android 9+)',
  },

  indications_for_use: {
    cleared_indication: 'The CardioWatch X1 is indicated for use in adult patients (18 years and older) for continuous ambulatory ECG monitoring for periods up to 14 days. The device is intended to detect, record, and transmit cardiac arrhythmias, including atrial fibrillation, atrial flutter, supraventricular tachycardia, and bradyarrhythmias, under the direction of a licensed healthcare provider.',
    contraindications: [
      'Not intended for use in patients with implanted cardiac devices (pacemakers, ICDs, CRT) — ECG interpretation may be unreliable',
      'Not indicated for paediatric patients (under 18 years)',
      'Not intended as a substitute for in-hospital ECG monitoring in acute cardiac events',
      'Not intended for surgical site placement or use in MRI environments',
    ],
    intended_environment: 'Ambulatory / outpatient use. Professional healthcare oversight required for clinical interpretation.',
  },

  predicate_devices: [
    {
      name: 'CardioSense Pro Monitor',
      k_number: 'K192834',
      applicant: 'CardioSense Medical Ltd.',
      cleared: 'March 2019',
      technological_similarity: 'Single-lead patch ECG with PPG-based AF detection algorithm. Equivalent electrode configuration, lead placement, and algorithm functional design.',
      intended_use_similarity: 'Adult ambulatory cardiac monitoring up to 14 days, AF detection and alerting under physician direction.',
      differences: 'CardioWatch X1 incorporates an updated adaptive algorithm (v2.1) with improved sensitivity in low-perfusion states. Battery life extended from 10 to 14 days. Bluetooth 5.2 vs. 4.2.',
      equivalence_conclusion: 'Substantially equivalent — same technological characteristics with same intended use.',
    },
    {
      name: 'VitalTrack ECG',
      k_number: 'K201567',
      applicant: 'VitalDx Corp.',
      cleared: 'September 2020',
      technological_similarity: 'Single-lead dry electrode patch ECG, PPG heart rate monitoring. Comparable signal acquisition and wireless data transmission architecture.',
      intended_use_similarity: 'Continuous ambulatory cardiac monitoring, arrhythmia detection in adult patients.',
      differences: 'CardioWatch X1 adds dual-wavelength PPG for SpO2 monitoring. AF-Detect algorithm adds real-time alerting not present in VitalTrack baseline model.',
      equivalence_conclusion: 'Substantially equivalent — same technological characteristics with same intended use.',
    },
    {
      name: 'PulseGuard 3000',
      k_number: 'K205891',
      applicant: 'Guardian MedTech Inc.',
      cleared: 'January 2021',
      technological_similarity: 'Wearable single-lead ECG patch, Bluetooth connectivity, ambulatory monitoring form factor.',
      intended_use_similarity: 'Adult cardiac rhythm monitoring, ambulatory use up to 14 days.',
      differences: 'CardioWatch X1 adds PPG-based AF detection layer. Different algorithm architecture; AF-Detect v2.1 is not based on PulseGuard 3000 algorithm.',
      equivalence_conclusion: 'Substantially equivalent — same intended use with minor technological differences that do not raise new safety or effectiveness questions.',
    },
  ],

  substantial_equivalence: {
    conclusion: 'Substantially Equivalent',
    basis: 'The CardioWatch X1 has the same intended use and same technological characteristics as the three predicate devices identified above. Performance testing demonstrates that the device meets or exceeds predicate safety and effectiveness benchmarks. No new safety or effectiveness questions are raised by the identified technological differences.',
    clinical_data_summary: 'Performance data submitted includes: (1) analytical validation of the AF-Detect v2.1 algorithm against a 72-hour Holter-monitored reference dataset (n=328 subjects, 62 confirmed AF); AF detection sensitivity 96.2%, specificity 97.8%; (2) bench testing per IEC 60601-1 and IEC 60601-2-25; (3) biocompatibility testing per ISO 10993-1 for skin-contacting materials; (4) electrical safety and EMC per IEC 60601-1-2:2014/AMD1:2020.',
    risk_summary: [
      {
        risk: 'False-negative AF detection',
        severity: 'High',
        mitigation: 'Algorithm trained on dataset including low-perfusion, atrial flutter, and pacemaker-artifact scenarios. Residual false-negative rate <4% in validation cohort. IFU excludes pacemaker patients.',
      },
      {
        risk: 'Skin irritation / allergic reaction',
        severity: 'Low',
        mitigation: 'Medical-grade silicone housing and latex-free hydrogel electrodes. ISO 10993-5 cytotoxicity and ISO 10993-10 sensitisation testing passed. Patch not intended for continuous wear >14 days.',
      },
      {
        risk: 'Missed arrhythmia due to signal artefact',
        severity: 'Medium',
        mitigation: 'Motion artefact rejection algorithm integrated into AF-Detect v2.1. Signal quality indicator displayed in companion app; clinician prompted to replace patch if signal quality persistently poor.',
      },
    ],
  },

  performance_summary: {
    af_detection: { sensitivity: '96.2%', specificity: '97.8%', ppv: '94.1%', npv: '98.4%', dataset: '328 subjects, 72h Holter reference' },
    battery_life: '14.2 days avg (simulated continuous ECG+PPG at 25°C)',
    data_integrity: '99.7% successful transmission rate over 14-day monitoring period in clinical study',
    electrode_adhesion: '94.3% patches remained adhered throughout 14-day wear period in 45-subject adhesion study',
    water_resistance: 'IP67 verified per IEC 60529',
  },

  regulatory_history: {
    prior_submissions: 'No prior submissions for this device.',
    eu_status: 'CE Marking under EU MDR 2017/745 — Certificate EU-CE-2022-0471 · Class IIb · Notified Body: BSI (NB 0086) · Valid to: November 2026',
    au_status: 'TGA ARTG Entry 355891 — Active',
    in_status: 'CDSCO Registration MD-IN-2023-4423 — Active',
    post_market_plan: 'PMCF study (CardioWatch MONITOR Registry, n=500, 24-month follow-up) initiated Q1 2022. Annual PSUR/CER cycle. EU MDR Article 85 PSUR submitted annually.',
  },
}

export const PARSE_STEPS = [
  { label: 'Identifying document type',     result: '510(k) Premarket Notification',              duration: 400  },
  { label: 'Extracting device name',         result: 'CardioWatch X1 · CardioTech Diagnostics',    duration: 350  },
  { label: 'Reading 510(k) number',          result: 'K213456 · Cleared Nov 2021',                 duration: 300  },
  { label: 'Parsing device classification',  result: 'Class II · 21 CFR 870.2900 · Cardiovascular', duration: 450 },
  { label: 'Identifying predicate devices',  result: '3 predicates found (K192834, K201567, K205891)', duration: 600 },
  { label: 'Extracting intended use',        result: 'AF detection · Adult ambulatory · ≤14 days',  duration: 350  },
  { label: 'Scanning risk profile',          result: '3 failure modes identified · 1 high severity',duration: 500  },
  { label: 'Mapping regulatory markets',     result: 'US · EU (IIb) · AU · IN — 4 active markets', duration: 400  },
  { label: 'Building surveillance context',  result: 'Device context ready',                        duration: 300  },
]