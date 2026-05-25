# A8’ — Wow-Moment Candidate Shortlist (Artifacts Corpus)

**Build date**: 2026-05-19
**Source**: `data/_scratch/artifacts.jsonl`
**Records read**: 49,735
**Excluded** (website-error / relevance<5 / no-title / no-link / invalid-pub-date): 33,976
**Scored**: 15,759
**Output**: `data/wow-candidates.json` (top 50)

## Top-50 Jurisdiction Breakdown

| Bucket | Count |
|---|---|
| US federal (`topic_jurisdiction_code == "US"` or `jurisdiction_tier_label == "us_federal"`) | 26 |
| US state (`US-XX`) | 15 |
| International | 9 |
| Recognition bonus fired | 14 |

## Scoring Formula

```
score = 0.30 * urgency + 0.20 * impact + 0.15 * recency + 0.15 * update_type + 0.10 * jurisdiction + 0.10 * recognition
```

`*` prefix in Title column = recognition score fired (PM platform name in title/entities/regulator_name).

## Top-15 Table

```
 #  Score  Pub Date       U     I   Rec  Type                Regulator                               Title
-------------------------------------------------------------------------------------------------------------------------------------------------
 1   9.00  2026-05-18  10.0  10.0  10.0  enforcement         Department of Financial Protection an    DFPI Shuts Down Crypto Kiosk Operator for Cheating Consume
 2   8.50  2026-05-01   9.0   8.0   8.0  proposed rule       U.S. Commodity Futures Trading Commis   *05.01.2026 - Amendments to Market Maker Program - FEX
 3   8.50  2026-05-14   9.0   9.0  10.0  final rule          Division of Insurance                    Governor Healey Announces Final Regs That Eliminate Prior 
 4   8.30  2026-05-19   9.0   9.0  10.0  enforcement         Commodity Futures Trading Commission     CFTC Sues Minnesota to Block State Law
 5   8.20  2026-05-15   9.0   8.0  10.0  bulletin            Commodity Futures Trading Commission    *ETRON | ElectronX is self-certifying its MISO & CAISO Core
 6   8.20  2026-05-05   9.0   9.0   8.0  final rule          New Jersey Department of Labor and Wo    2026-05-05 - NJDOL Adopts Clear Rules on Worker Classifica
 7   8.10  2026-04-30   9.0   9.0   8.0  bulletin            Commodity Futures Trading Commission    *04.30.2026 - Updated Rulebook - REX
 8   8.10  2026-05-13   9.0   8.0  10.0  final rule          Commodity Futures Trading Commission     CBOT | Issuance of CME Group Market RegulationAdvisory Not
 9   8.10  2026-05-13   9.0   8.0  10.0  final rule          Commodity Futures Trading Commission     COMEX | Issuance of CME Group MarketRegulation Advisory No
10   8.05  2026-04-17  10.0   9.0   5.0  enforcement         Department of Financial Protection an    UMETEACA Inc.
11   8.00  2026-05-01   9.0   9.0   8.0  final rule          Commodity Futures Trading Commission     05.01.2026 - Issuance of CME Group Market Regulation Advis
12   8.00  2026-05-14   9.0   8.0  10.0  proposed rule       California Department of Justice         California Department of Justice Releases Proposed "Protec
13   8.00  2026-05-14   9.0   8.0  10.0  proposed rule       California Department of Justice         California Department of Justice Releases Proposed "Protec
14   8.00  2026-05-13   8.0   9.0  10.0  enforcement         Securities and Exchange Commission       David H. Goldman
15   7.90  2026-05-01  10.0   9.0   8.0  enforcement         Alberta Securities Commission            NU E Power Corp.
```

## Observations & Concerns

- Regulator spread looks healthy; top regulator ('Commodity Futures Trading Commission') has 6/15 entries.
- Recency looks good: 15/15 entries are within 60 days.
- Recognition score fired on 3/15 top-15 entries — PM platform names appear in title, entities, or regulator_name.

## Top Picks — Curation Notes

### 1. DFPI Shuts Down Crypto Kiosk Operator for Cheating Consumers and Violating State Laws
- **Regulator**: Department of Financial Protection and Innovation
- **Date**: 2026-05-18 | **Type**: enforcement
- **Score**: 9.00 (U=10.0, I=10.0, rec=10)
- **Link**: https://dfpi.ca.gov/press_release/dfpi-shuts-down-crypto-kiosk-operator-for-cheating-consumers-and-violating-state-laws/
- **What changed**: DFPI ordered Anh Management LLC (Hermes Bitcoin) to cease all digital financial asset kiosk operations in California due to violations including excessive fees, transaction limits breaches, inadequate disclosures, and AML program failures.
- **Entities**: Anh Management LLC, Coinme, Inc, DFPI, Hermes Bitcoin, KC Mohseni

### 2. 05.01.2026 - Amendments to Market Maker Program - FEX
- **Regulator**: U.S. Commodity Futures Trading Commission
- **Date**: 2026-05-01 | **Type**: proposed rule
- **Score**: 8.50 (U=9.0, I=8.0, rec=8)
- **Link**: https://www.cftc.gov/IndustryOversight/IndustryFilings/TradingOrganizationRules/60682
- **What changed**: Changes to quoting obligations under the Market Maker program affecting ForecastEx LLC as a designated contract market and clearinghouse.
- **Entities**: Commodity Futures Trading Commission, ForecastEx LLC, Graham Deese, U.S. Commodity Futures Trading Commission

### 3. Governor Healey Announces Final Regs That Eliminate Prior Authorization Requirements for Routine and Essential Health Care
- **Regulator**: Division of Insurance
- **Date**: 2026-05-14 | **Type**: final rule
- **Score**: 8.50 (U=9.0, I=9.0, rec=10)
- **Link**: https://www.mass.gov/news/governor-healey-announces-final-regs-that-eliminate-prior-authorization-requirements-for-routine-and-essential-health-care
- **What changed**: Finalized regulations remove prior authorization for cancer scans, medications for chronic conditions, radiology imaging after cancer diagnosis, and other essential services, impacting insurers, providers, and patients.
- **Entities**: Dana-Farber Cancer Institute, Division of Insurance, Fallon Health, Health Care for All, Health Law Advocates

### 4. CFTC Sues Minnesota to Block State Law
- **Regulator**: Commodity Futures Trading Commission
- **Date**: 2026-05-19 | **Type**: enforcement
- **Score**: 8.30 (U=9.0, I=9.0, rec=10)
- **Link**: https://www.cftc.gov/PressRoom/PressReleases/9233-26
- **What changed**: The CFTC filed a lawsuit seeking to prevent Minnesota's law from taking effect on August 1, 2026, which would criminalize prediction market activities as felonies.
- **Entities**: Arizona, Connecticut, Commodity Futures Trading Commission, Illinois, Massachusetts

### 5. ETRON | ElectronX is self-certifying its MISO & CAISO Core Liquidity Provider Program | [3]
- **Regulator**: Commodity Futures Trading Commission
- **Date**: 2026-05-15 | **Type**: bulletin
- **Score**: 8.20 (U=9.0, I=8.0, rec=10)
- **Link**: https://www.cftc.gov/IndustryOversight/IndustryFilings/TradingOrganizationRules/60808
- **What changed**: ElectronX self-certifies its MISO and CAISO Core Liquidity Provider Program effective June 1, 2026, introducing eligibility criteria, obligations, incentives, and monitoring for participants.
- **Entities**: Christopher J. Kirkpatrick, Commodity Futures Trading Commission, Dan Hoban, Electron Exchange DCM, LLC, ElectronX

