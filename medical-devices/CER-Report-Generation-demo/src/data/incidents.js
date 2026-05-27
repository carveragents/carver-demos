// Mock incident data keyed by device id.
// Sources: MAUDE (US), MHRA (UK), Swissmedic (Swiss)
// Replace with real JSON payloads per country when available.

export const INCIDENTS = {
  1: [
    { date: "2024-11", src: "MAUDE",      desc: "Inappropriate shock – T-wave oversensing",             device: "Sprint Fidelis Lead",   sev: "high" },
    { date: "2024-10", src: "MAUDE",      desc: "Lead conductor fracture, no shock delivered",           device: "Sprint Fidelis Lead",   sev: "high" },
    { date: "2024-09", src: "Swissmedic", desc: "Premature battery depletion at 3yr follow-up",          device: "Viva XT CRT-D",         sev: "high" },
    { date: "2024-09", src: "MAUDE",      desc: "Pocket infection requiring device explant",              device: "ICD Gen device",        sev: "med"  },
    { date: "2024-08", src: "MHRA",       desc: "Noise on RV channel, oversensing inhibition",           device: "Evoque ICD",            sev: "med"  },
    { date: "2024-07", src: "MHRA",       desc: "Device reset after MRI conditional scan",               device: "ICD MRI conditional",   sev: "med"  },
    { date: "2024-06", src: "MAUDE",      desc: "Subthreshold shock – patient pain complaint",           device: "Zephyr DR",             sev: "low"  },
    { date: "2024-05", src: "Swissmedic", desc: "Programming interface timeout, no patient harm",        device: "Programmer 2090",       sev: "low"  },
  ],
  2: [
    { date: "2024-11", src: "MAUDE",      desc: "ARMD – severe metallosis requiring revision surgery",   device: "ASR XL MoM",            sev: "high" },
    { date: "2024-10", src: "MAUDE",      desc: "Cobalt ions > 7 ppb, neurological symptoms reported",  device: "Pinnacle MoM",          sev: "high" },
    { date: "2024-10", src: "MHRA",       desc: "Aseptic loosening at 5yr follow-up, revision required",device: "Corail hip stem",        sev: "high" },
    { date: "2024-09", src: "Swissmedic", desc: "Periprosthetic pseudotumour, 4cm diameter",            device: "ASR resurfacing",       sev: "high" },
    { date: "2024-08", src: "MAUDE",      desc: "Elevated serum chromium – patient monitoring ongoing",  device: "Pinnacle MoM",          sev: "med"  },
    { date: "2024-07", src: "MHRA",       desc: "Squeaking noise, no mechanical failure detected",       device: "MoM total hip",         sev: "low"  },
  ],
  3: [
    { date: "2024-10", src: "MAUDE",      desc: "Calibration drift – readings 15% below lab reference", device: "FreeStyle Libre 3",     sev: "med"  },
    { date: "2024-08", src: "MHRA",       desc: "Adhesive reaction, grade 2 skin irritation",            device: "FreeStyle Libre 2",     sev: "low"  },
    { date: "2024-06", src: "MAUDE",      desc: "Sensor delamination, loss of signal at day 8",          device: "FreeStyle Libre 3",     sev: "low"  },
    { date: "2024-05", src: "Swissmedic", desc: "App connectivity failure, 45-min data gap",             device: "FreeStyle Libre reader",sev: "low"  },
  ],
  4: [
    { date: "2024-11", src: "MAUDE",      desc: "Lead migration – therapy suboptimal, revision needed",  device: "Precision Spectra SCS", sev: "high" },
    { date: "2024-10", src: "MAUDE",      desc: "Paresthesia change, amplitude threshold increase",       device: "WaveWriter Alpha SCS",  sev: "med"  },
    { date: "2024-08", src: "Swissmedic", desc: "Battery longevity 18 months below projected 5 years",  device: "Precision Plus",        sev: "med"  },
    { date: "2024-07", src: "MHRA",       desc: "Stimulation loss – connector set corrosion suspected",  device: "WaveWriter Alpha SCS",  sev: "med"  },
    { date: "2024-06", src: "MAUDE",      desc: "Infection at implant site requiring partial revision",   device: "SCS IPG",               sev: "low"  },
  ],
}
