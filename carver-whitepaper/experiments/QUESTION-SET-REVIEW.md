# Question set for sign-off — cost/accuracy/latency experiment

**26 questions** · model `openai/gpt-5.6-sol` · corpus snapshot 2026-07-27 (229,287 indexed records)

**Status:** AWAITING USER SIGN-OFF — no arm may run until this file is approved and committed

**Arms:** `baseline` · `web` · `carver-full` · `carver-domain`

**Cutoff doctrine:** pre-cutoff questions use obligations settled by 2024-06 that are STILL IN FORCE in 2026; post-cutoff questions use records dated 2026. The 2024-07 .. 2025-12 band is deliberately left empty so neither stratum depends on a contested cutoff date.

**Known bias:** questions are sourced FROM the corpus, so the Carver arms are advantaged by construction. Mitigations: (a) every chosen obligation is public and published on the issuing body's own site, so the web arm can reach it; (b) the pre-cutoff stratum is chosen so baseline should score well; (c) results are reported per stratum, never pooled into a single headline. This limitation is stated in the report, not buried.


---


## head-pre-cutoff  (8 questions)


### q01 · medical-devices

**Ground truth:** Regulation EU 2023 607  

European Parliament and Council of the European Union · 2023-03-20  

<https://eur-lex.europa.eu/eli/reg/2023/607/oj>


**System (operator context):**  

> You are the assistant for the regulatory-affairs team at a medical-device manufacturer. About the company:

> it holds a portfolio of Class IIb devices still covered by certificates issued under the old Medical Devices

> Directive, and sells them across the EU. The person you are speaking with is on the regulatory-affairs team.

> Today's date is 10 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're putting together the portfolio plan for the next two years. Is there anything we need to settle for

> these older product lines, or can we keep supplying them as we are?


**Pre-registered keys**

- **Controlling obligation:** Regulation (EU) 2023/607 extended the validity of MDD/AIMDD certificates and the MDR transitional periods, but only on conditions

- **Citation:** Regulation (EU) 2023/607 (amending Regulation (EU) 2017/745)

- **Dates:** quality management system in place by 26 May 2024; formal conformity-assessment application lodged by 26 May 2024; written agreement with a notified body signed by 26 September 2024; extended transitional end dates differ by risk class (2027/2028)

- **Jurisdiction:** European Union

- **Scope / threshold:** extension is conditional — devices that missed the QMS/application/agreement milestones do not benefit

- **Required action:** confirm the conditions were met; otherwise the device cannot continue to be placed on the market under the legacy certificate


**Checks (8):** regex — controlling-obligation, actionable, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, temporal-validity, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q02 · medical-devices

**Ground truth:** Wegleitung Vorkommnismeldung Anwender  

Swissmedic · 2023-11-01  

<https://www.swissmedic.ch/swissmedic/de/home/medizinprodukte/vorkommnisse---fsca-melden--materiovigilance-/anwender---be>


**System (operator context):**  

> You are the assistant for the clinical-engineering team at a hospital group in Switzerland. About the

> organisation: it operates several acute-care hospitals and uses a large installed base of medical devices

> and in-vitro diagnostics across its wards and laboratories. The person you are speaking with manages the

> clinical-engineering team. Today's date is 12 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're rewriting our internal incident-handling playbook this quarter. Is there anything we're obliged to do

> when something goes wrong with a device on the ward?


**Pre-registered keys**

- **Controlling obligation:** professional users must report serious incidents to Swissmedic AND to the supplier

- **Citation:** Medical Devices Ordinance (MepV/MedDO) and In-vitro Diagnostics Ordinance (IvDV/IvDO)

- **Jurisdiction:** Switzerland

- **Scope / threshold:** duty attaches to SERIOUS incidents; professional users specifically

- **Required action:** report to Swissmedic and supplier on the prescribed form; hospitals must notify Swissmedic of vigilance contact persons; GPMV-Spital / GPMV-IVD good practice applies


**Checks (8):** regex — controlling-obligation, jurisdiction-overlay, scope-boundary, provenance · judge — actionable, cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q03 · crypto-assets

**Ground truth:** New Directive on tax transparency to help Member States shine a light on the crypto asset sector  

Directorate-General for Taxation and Customs Union · 2023-10-17  

<https://taxation-customs.ec.europa.eu/news/new-directive-tax-transparency-help-member-states-shine-light-crypto-asset-se>


**System (operator context):**  

> You are the assistant for the finance team at a crypto-asset firm. About the company: it is established in

> Ireland and provides exchange and transfer services for crypto-assets to clients across the EU, most of whom

> are EU residents. The person you are speaking with works in the finance team. Today's date is 15 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're scoping the finance systems roadmap for next year. Is there anything on the reporting side we should

> be building for?


**Pre-registered keys**

- **Controlling obligation:** DAC8 requires crypto-asset service providers in the EU to report transactions of EU-resident clients

- **Citation:** DAC8 — Council Directive amending Directive 2011/16/EU on administrative cooperation (adopted 17 October 2023)

- **Dates:** adopted 17 October 2023; reporting applies from 1 January 2026

- **Jurisdiction:** European Union

- **Scope / threshold:** covers CASPs and extends to financial institutions for e-money and CBDC

- **Required action:** build client tax-residence collection and transaction reporting; automatic exchange of information between Member States


**Checks (8):** regex — controlling-obligation, actionable, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, temporal-validity, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q04 · crypto-assets

**Ground truth:** Final Report Guidelines Amending Guidelines on MLTF Risk Factors  

European Banking Authority · 2024-01-16  

<https://www.eba.europa.eu/legacy/regulation-and-policy/regulatory-activities/anti-money-laundering-and-countering-financ>


**System (operator context):**  

> You are the assistant for the financial-crime team at a bank. About the company: it is an EU credit

> institution that provides banking services to corporate clients, several of which are firms offering crypto-

> asset services. The person you are speaking with is on the financial-crime team. Today's date is 16 June

> 2026.


**User (names no rule, deadline, or regulator):**  

> We're refreshing our client risk-assessment methodology this cycle. Is there anything we should be factoring

> in that we might not have before?


**Pre-registered keys**

- **Controlling obligation:** EBA ML/TF Risk Factors Guidelines were amended to insert crypto-asset specific risk factors and sectoral guidance for CASPs

- **Citation:** EBA Guidelines amending the ML/TF Risk Factors Guidelines (EBA/GL/2024/01), 16 January 2024

- **Dates:** published 16 January 2024

- **Jurisdiction:** European Union / EEA

- **Scope / threshold:** applies to credit and financial institutions dealing WITH CASPs, including CASPs not authorised under Regulation (EU) 2023/1114

- **Required action:** apply the crypto-specific risk factors in customer risk assessment and due diligence


**Checks (7):** regex — controlling-obligation, jurisdiction-overlay, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q05 · state-lending

**Ground truth:** Cyber Incident Notification Requirements  

National Credit Union Administration · 2023-08-01  

<https://ncua.gov/regulation-supervision/letters-credit-unions-other-guidance/cyber-incident-notification-requirements>


**System (operator context):**  

> You are the assistant for the operations team at a federally insured credit union in the United States.

> About the organisation: it serves retail members, runs online and mobile banking, and depends on several

> third-party technology providers. The person you are speaking with is on the operations team. Today's date

> is 17 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're updating our incident-response runbook. Beyond containing the problem, is there anything else we'd

> need to do if we had a serious IT security event?


**Pre-registered keys**

- **Controlling obligation:** federally insured credit unions must notify the NCUA of a reportable cyber incident

- **Citation:** NCUA cyber incident notification rule (12 CFR Part 748)

- **Dates:** no later than 72 hours after reasonable belief that a reportable cyber incident occurred; effective 1 September 2023

- **Jurisdiction:** United States — federally insured credit unions

- **Scope / threshold:** reportable cyber incident: loss of confidentiality/integrity/availability, disruption of operations, or a third-party notification

- **Required action:** notify NCUA within 72 hours via phone, secure email, or the online form


**Checks (8):** regex — controlling-obligation, actionable, jurisdiction-overlay, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q06 · state-lending

**Ground truth:** Second Amendment to 23 NYCRR 500 Cybersecurity Requirements for Financial Services Companies  

New York State Department of Financial Services · 2023-11-01  

<https://www.dfs.ny.gov/industry_guidance/regulations/final_adoptions_fs/rf_fs_2amend23NYCRR500_text_20231101_alt>


**System (operator context):**  

> You are the assistant for the technology team at a financial-services company. About the company: it is

> licensed by the New York State Department of Financial Services and provides consumer lending products to

> customers in New York and several other states. The person you are speaking with is on the technology team.

> Today's date is 18 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're planning the security workstream for the coming year. Is there anything we're on the hook for that

> should shape what we prioritise?


**Pre-registered keys**

- **Controlling obligation:** the Second Amendment to 23 NYCRR Part 500 imposes an expanded cybersecurity programme on covered entities

- **Citation:** 23 NYCRR Part 500 (Second Amendment), effective 1 November 2023

- **Dates:** effective 1 November 2023; phased compliance deadlines from one month to two years after the effective date

- **Jurisdiction:** New York State (NYDFS-regulated entities)

- **Scope / threshold:** heightened obligations for Class A companies (independent audits, privileged-access monitoring)

- **Required action:** maintain a risk-assessment-based cybersecurity programme; designate a CISO; governance, vulnerability management, audit trails, access controls, application security


**Checks (8):** regex — controlling-obligation, jurisdiction-overlay, actionable, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, temporal-validity  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q07 · child-safety

**Ground truth:** Article 29 Working Party Guidelines on transparency under Regulation 2016 679  

European Data Protection Board · 2018-04-11  

<https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/transparency_en>


**System (operator context):**  

> You are the assistant for the product team at a company that runs a general-audience mobile app. About the

> product: it is available across the EU, collects personal data from its users, and a meaningful share of its

> users are children. The person you are speaking with is a product manager. Today's date is 19 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're redesigning our onboarding flow and the screens that explain what we do with people's data. Is there

> anything we need to get right there?


**Pre-registered keys**

- **Controlling obligation:** transparency obligations under GDPR Articles 12–14, as elaborated by the EDPB transparency guidelines

- **Citation:** GDPR Articles 12–14; WP29/EDPB Guidelines on transparency under Regulation 2016/679

- **Jurisdiction:** European Union

- **Scope / threshold:** clear and plain language is required ESPECIALLY where the audience includes children and vulnerable people

- **Required action:** information must be concise, transparent, intelligible, easily accessible, in clear and plain language; provided in writing or other means including electronically


**Checks (8):** regex — controlling-obligation, jurisdiction-overlay, scope-boundary, actionable, provenance · judge — cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q08 · child-safety

**Ground truth:** Guidelines 4 2019 on Article 25 Data Protection by Design and by Default Version 2.0  

European Data Protection Board · 2020-10-20  

<https://edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-42019-article-25-data-protection-design-a>


**System (operator context):**  

> You are the assistant for the engineering team at a small software company in the EU. About the company: it

> is building a new consumer product from scratch that will process personal data, and the team is still

> choosing its architecture and default settings. The person you are speaking with is an engineer. Today's

> date is 22 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're at the architecture stage and locking in defaults. Is there anything we should be considering now

> rather than later?


**Pre-registered keys**

- **Controlling obligation:** data protection by design and by default under GDPR Article 25

- **Citation:** GDPR Article 25; EDPB Guidelines 4/2019 on Article 25, Version 2.0

- **Jurisdiction:** European Union

- **Scope / threshold:** applies to ALL controllers regardless of size — no small-company exemption

- **Required action:** implement appropriate technical and organisational measures; consider state of the art; demonstrate effectiveness through documentation and KPIs


**Checks (8):** regex — controlling-obligation, jurisdiction-overlay, actionable, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


## head-post-cutoff  (10 questions)


### q09 · medical-devices

**Ground truth:** swissdamed Service Agreement  

Swissmedic · 2026-03-27  

<https://www.swissmedic.ch/dam/swissmedic/en/dokumente/medizinprodukte/mep_urr/bw630_40_871d_wl_dienstleistungvereinbarung_swissdamed.pdf.download.pdf/BW630_40_871e_WL_swissdamed_Service_Agreement.pdf>


**System (operator context):**  

> You are the assistant for the regulatory-affairs team at a medical-device manufacturer. About the company:

> it makes in-vitro diagnostic devices and places them on the Swiss market through a local authorised

> representative. The person you are speaking with is on the regulatory-affairs team. Today's date is 20 June

> 2026.


**User (names no rule, deadline, or regulator):**  

> We're refreshing our market-access checklist for the next quarter. Is there anything we need to take care of

> to keep supplying our current markets?


**Pre-registered keys**

- **Controlling obligation:** device registration in swissdamed becomes mandatory

- **Citation:** swissdamed Service Agreement v4.0 (Swissmedic); MepV/MedDO and IvDV/IvDO

- **Dates:** device registration requirement effective from 1 July 2026; service agreement version 4.0 valid from 27 March 2026

- **Jurisdiction:** Switzerland

- **Scope / threshold:** economic operators must register their roles separately to obtain a CHRN

- **Required action:** register the company and economic-operator roles via swissdamed using AGOV or CH-LOGIN; obtain CHRN; register products with market status


**Checks (8):** regex — controlling-obligation, actionable, jurisdiction-overlay, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, temporal-validity  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q10 · medical-devices

**Ground truth:** About UDI Australia  

Therapeutic Goods Administration · 2026-06-22  

<https://www.tga.gov.au/products/medical-devices/labelling-and-advertising/unique-device-identification-udi-hub/about-udi-australia>


**System (operator context):**  

> You are the assistant for the regulatory-affairs team at a medical-device manufacturer. About the company:

> it holds Australian Register of Therapeutic Goods entries for a range of devices and supplies them into

> Australia through a local sponsor. The person you are speaking with is on the regulatory-affairs team.

> Today's date is 25 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're planning label and packaging artwork changes for the next production cycle. Is there anything coming

> that we should fold into that work?


**Pre-registered keys**

- **Controlling obligation:** mandatory Unique Device Identification labelling and data submission to the Australian UDI Database

- **Citation:** TGA UDI Australia; AusUDID

- **Dates:** compliance dates vary by device risk class from 1 July 2026 to 1 July 2029

- **Jurisdiction:** Australia

- **Scope / threshold:** phased by device risk class

- **Required action:** put a human- and machine-readable UDI on labels and packaging; submit and maintain device data in AusUDID


**Checks (8):** regex — controlling-obligation, actionable, jurisdiction-overlay, scope-boundary, provenance · judge — cite-real, no-fabricated-obligation, temporal-validity  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q11 · medical-devices

**Ground truth:** Déclarer une rupture ou un arrêt de commercialisation d un dispositif médical ou d un dispositif médical de diagnostic in vitro  

ANSM · 2026-05-29  

<https://ansm.sante.fr/vos-demarches/industriel/declarer-une-rupture-dans-la-disponibilite-dun-dispositif-medical-ou-dun-dispositif-medical-de-diagnostic-in-vitro-indispensable>


**System (operator context):**  

> You are the assistant for the supply-chain team at a medical-device manufacturer. About the company: it is

> headquartered in France and supplies devices used in hospital critical care across Europe. It is planning to

> discontinue one of its older product lines and to pause production of another while it changes component

> supplier. The person you are speaking with is on the supply-chain team. Today's date is 26 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're sequencing the product transitions for the next year. Is there anything we need to line up before we

> make these changes?


**Pre-registered keys**

- **Controlling obligation:** manufacturers must give advance notice of an interruption or permanent cessation of supply that could cause serious harm

- **Citation:** Regulations (EU) 2017/745 and 2017/746 as amended in June 2024; ANSM notification procedure

- **Dates:** at least 6 months before the interruption or cessation

- **Jurisdiction:** France / European Union

- **Scope / threshold:** duty attaches where the interruption could cause serious harm or risk; non-EU manufacturers notify the authority of their European representative

- **Required action:** notify ANSM at least 6 months in advance using the common European information exchange form


**Checks (8):** regex — controlling-obligation, actionable, jurisdiction-overlay, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q12 · crypto-assets

**Ground truth:** Attentes de l'ACPR en vue de l'agrément en qualité d'établissement de paiement des prestataires offrant des services sur crypto-actifs portant sur des jetons de monnaie électronique  

Autorité de Contrôle Prudentiel et de Résolution (ACPR) · 2026-02-19  

<https://acpr.banque-france.fr/fr/actualites/attentes-de-lacpr-en-vue-de-lagrement-en-qualite-detablissement-de-paiement-des-prestataires-offrant>


**System (operator context):**  

> You are the assistant for the operations team at a crypto-asset firm. About the company: it is established

> in France, holds a MiCA authorisation as a crypto-asset service provider, and offers custody and transfer

> services for e-money tokens to its clients. The person you are speaking with is on the operations team.

> Today's date is 29 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're locking down the plan for the second half of the year. Is there anything outstanding on the regulatory

> side, or are we fine to keep running the service as it is?


**Pre-registered keys**

- **Controlling obligation:** EMT-related crypto-asset services count as payment services and require payment-institution authorisation under PSD2 — a MiCA authorisation is not sufficient

- **Citation:** ACPR expectations on payment-institution authorisation for CASPs offering EMT services; PSD2; MiCA

- **Dates:** no-action transition until 2 March 2026; 1 July 2026 for certain transitional regimes

- **Jurisdiction:** France

- **Scope / threshold:** applies to EMT-related transfers and custody carried out on behalf of clients

- **Required action:** obtain payment-institution (établissement de paiement) authorisation under PSD2 via the streamlined process leveraging MiCA information


**Checks (8):** regex — controlling-obligation, jurisdiction-overlay, actionable, scope-boundary, provenance · judge — cite-real, no-fabricated-obligation, temporal-validity  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q13 · crypto-assets

**Ground truth:** Bank of England and Financial Conduct Authority's approach to joint regulation of systemic stablecoin issuers  

Bank of England · 2026-06-30  

<https://www.bankofengland.co.uk/paper/2026/boe-and-fcas-approach-to-joint-regulation-of-systemic-stablecoin-issuers>


**System (operator context):**  

> You are the assistant for the strategy team at a payments company. About the company: it is based in the

> United Kingdom and issues a sterling-denominated stablecoin that is increasingly used for everyday retail

> payments, with volumes growing quickly. The person you are speaking with is on the strategy team. Today's

> date is 3 July 2026.


**User (names no rule, deadline, or regulator):**  

> We're putting together the board pack on where the business goes next. Is there anything on the regulatory

> side the board should know about?


**Pre-registered keys**

- **Controlling obligation:** stablecoin issuers recognised as systemic by HM Treasury fall under joint Bank of England and FCA regulation

- **Citation:** Bank of England and FCA approach to joint regulation of systemic stablecoin issuers (30 June 2026)

- **Dates:** published 30 June 2026

- **Jurisdiction:** United Kingdom

- **Scope / threshold:** triggered by recognition as SYSTEMIC by HM Treasury — growth in payments use is what brings it into scope

- **Required action:** prepare for Bank prudential and operational requirements — backing assets, capital and reserves, safeguarding, issuance guardrails — with FCA continuing on conduct, market integrity and competition


**Checks (8):** regex — controlling-obligation, jurisdiction-overlay, actionable, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q14 · crypto-assets

**Ground truth:** MiCA CNB grants crypto licences to 11 entities  

Czech National Bank · 2026-07-01  

<https://www.cnb.cz/en/cnb-news/press-releases/MiCA-CNB-grants-crypto-licences-to-11-entities/>


**System (operator context):**  

> You are the assistant for the operations team at a crypto-asset company. About the company: it offers

> custody and exchange services for crypto-assets to retail clients and is established in Czechia. It has

> operated since 2022 under a local trade registration and holds no crypto-specific authorisation. The person

> you are speaking with is on the operations team. Today's date is 6 July 2026.


**User (names no rule, deadline, or regulator):**  

> We're finalising the operating plan for the rest of the year. Is there anything we need to sort out, or can

> we carry on as we are?


**Pre-registered keys**

- **Controlling obligation:** only entities authorised under MiCA by an EU competent authority may provide crypto-asset services; unauthorised providers must cease and wind down

- **Citation:** MiCA (Regulation (EU) 2023/1114); Czech National Bank

- **Dates:** from 1 July 2026 authorisation is required; transitional period has ended

- **Jurisdiction:** Czechia / European Union

- **Scope / threshold:** a local trade registration is not a MiCA authorisation

- **Required action:** immediately stop onboarding new clients and cease marketing; limit activity to orderly wind-down including asset transfer and position closure


**Checks (8):** regex — controlling-obligation, actionable, jurisdiction-overlay, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, temporal-validity  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q15 · state-lending

**Ground truth:** OCC Issues Two Interim Final Actions Clarifying Bank Powers under Federal Law and the Preemption of a Related State Law  

Office of the Comptroller of the Currency · 2026-04-24  

<https://occ.gov/news-issuances/news-releases/2026/nr-occ-2026-32.html>


**System (operator context):**  

> You are the assistant for the payments team at a national bank in the United States. About the company: it

> is chartered as a national bank, issues consumer credit and debit cards, and earns interchange on card

> transactions in Illinois among other states. The person you are speaking with is on the payments team.

> Today's date is 1 July 2026.


**User (names no rule, deadline, or regulator):**  

> We're finalising the fee and interchange plan for the second half of the year. Is there anything that

> changes what we can and can't do?


**Pre-registered keys**

- **Controlling obligation:** federal law preempts the Illinois Interchange Fee Prohibition Act for national banks and federal savings associations

- **Citation:** OCC interim final rule and interim final order, 24 April 2026 (NR-OCC-2026-32)

- **Dates:** preemption order effective 1 July 2026; comments due within 30 days of Federal Register publication

- **Jurisdiction:** United States federal / Illinois

- **Scope / threshold:** applies to national banks and federal savings associations — not to state-chartered institutions

- **Required action:** national banks may charge non-interest fees including interchange even where set by or in consultation with third parties; the Illinois IFPA does not apply to them


**Checks (8):** regex — controlling-obligation, jurisdiction-overlay, actionable, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, temporal-validity  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q16 · state-lending

**Ground truth:** Insurance Circular Letter No. 1 2026 Disaster Planning Preparedness and Response by the Property Casualty Insurance Industry  

New York State Department of Financial Services · 2026-05-20  

<https://www.dfs.ny.gov/industry-guidance/circular-letters/cl2026-01>


**System (operator context):**  

> You are the assistant for the operations team at a property and casualty insurer. About the company: it is

> licensed in New York and writes homeowners and commercial property cover across the state. The person you

> are speaking with is on the operations team. Today's date is 24 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're reviewing our business-continuity documentation this quarter. Is there anything we're expected to have

> done or to file?


**Pre-registered keys**

- **Controlling obligation:** updated disaster planning, preparedness and response requirements, including filings

- **Citation:** NYDFS Insurance Circular Letter No. 1 (2026) — repeals and replaces Circular Letter No. 3 (2025)

- **Dates:** pre-disaster data survey due 11 June 2026; disaster response plan and questionnaires due 30 July 2026

- **Jurisdiction:** New York State

- **Scope / threshold:** property/casualty industry (a separate Circular Letter No. 2 covers life and health)

- **Required action:** submit the pre-disaster data survey and disaster response plan via the DFS ID portal; perform an annual business impact analysis; maintain updated BCP and disaster response plans


**Checks (8):** regex — controlling-obligation, jurisdiction-overlay, actionable, provenance · judge — temporal-validity, cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q17 · state-lending

**Ground truth:** FDIC Official Signs Advertisement of Membership False Advertising and Misrepresentation of Insured Status and Misuse of the FDIC's Name or Logo  

Federal Deposit Insurance Corporation · 2026-01-29  

<https://www.govinfo.gov/content/pkg/FR-2026-01-29/pdf/2026-01806.pdf>


**System (operator context):**  

> You are the assistant for the digital team at an insured depository institution in the United States. About

> the company: it takes deposits through its website and mobile app, and also markets investment products

> offered by a third party through the same logged-in experience. The person you are speaking with is on the

> digital team. Today's date is 30 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're rebuilding the app's navigation and account-opening screens. Is there anything we have to get right in

> that redesign?


**Pre-registered keys**

- **Controlling obligation:** FDIC official digital sign display requirements and non-deposit product signage on digital channels

- **Citation:** FDIC final rule, 12 CFR Part 328 (published 29 January 2026)

- **Dates:** compliance deadline extended — the report must record the exact extended date the arm states

- **Jurisdiction:** United States

- **Scope / threshold:** applies to digital deposit-taking channels and ATMs; distinct treatment for pages primarily dedicated to non-deposit products

- **Required action:** display the FDIC official digital sign clearly, continuously and conspicuously on initial, login and account-opening pages; display non-deposit signage; give a one-time notification when a logged-in customer navigates to a third-party non-deposit product


**Checks (8):** regex — controlling-obligation, actionable, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, temporal-validity, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q18 · child-safety

**Ground truth:** EDPS strengthens DPO role new guidance and binding rules to protect DPO independence across EU institutions  

European Data Protection Supervisor · 2026-02-16  

<https://idpc.org.mt/news-latest/edps-strengthens-dpo-role-new-guidance-and-binding-rules-to-protect-dpo-independence-acr>


**System (operator context):**  

> You are the assistant for the human-resources team at an EU institution. About the organisation: it

> processes personal data in the course of its work and has a designated Data Protection Officer whose current

> term still has time to run. The team is planning an internal reorganisation that would change several senior

> post-holders. The person you are speaking with is on the HR team. Today's date is 1 July 2026.


**User (names no rule, deadline, or regulator):**  

> We're mapping out the reorganisation and which roles change. Is there anything we need to be careful about

> in how we handle it?


**Pre-registered keys**

- **Controlling obligation:** prior consent of the EDPS is required before dismissing a DPO before the end of their term

- **Citation:** EDPS guidance on the role and independence of DPOs; EDPS Decision 01/2026

- **Dates:** announced 16 February 2026

- **Jurisdiction:** European Union institutions

- **Scope / threshold:** applies to dismissal BEFORE term end; designation and institutional positioning must follow EDPS guidance

- **Required action:** obtain EDPS prior consent before any dismissal of the DPO; follow the procedural framework in Decision 01/2026


**Checks (8):** regex — controlling-obligation, actionable, jurisdiction-overlay, provenance · judge — scope-boundary, cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


## tail-silent-trigger  (5 questions)


### q19 · medical-devices

**Ground truth:** Medtronic Inc FA1563 Nitron CryoConsole  

Inspectie Gezondheidszorg en Jeugd · 2026-05-27  

<https://www.igj.nl/documenten/fsn-2026/06/18/medtronic-inc-fa1563-nitron-cryoconsole>


**System (operator context):**  

> You are the assistant for the cardiac catheterisation lab at a hospital in the Netherlands. About the

> department: it runs a cryoablation programme using the Nitron CryoConsole with Arctic Front Advance and

> Arctic Front Advance PRO balloon catheters, and holds stock of those catheters. The person you are speaking

> with manages the lab. Today's date is 2 July 2026.


**User (names no rule, deadline, or regulator):**  

> We're planning the ablation list and stock ordering for the next few months. Is there anything we should

> factor in?


**Pre-registered keys**

- **Controlling obligation:** a field safety notice affects the catheters the department uses — they fail authentication after a set date

- **Citation:** Medtronic FSN FA1563 (Nitron CryoConsole), published via IGJ

- **Dates:** catheters fail authentication after 31 December 2025

- **Jurisdiction:** Netherlands / EU

- **Scope / threshold:** affects Arctic Front Advance and Arctic Front Advance PRO balloon catheters used with the Nitron CryoConsole

- **Required action:** treat affected stock as potentially unusable; act on the field safety notice


**Checks (6):** regex — controlling-obligation, actionable, provenance · judge — cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q20 · medical-devices

**Ground truth:** Urgent Field Safety Notice for INFINITT PACS 7.0 by Infinitt Co., Ltd.  

BfArM - Federal Institute for Drugs and Medical Devices · 2026-03-31  

<https://www.bfarm.de/SharedDocs/Kundeninfos/EN/17/2026/14094-26_kundeninfo_en.html?nn=986784>


**System (operator context):**  

> You are the assistant for the radiology department at a hospital in Germany. About the department: it reads

> and reports imaging studies on INFINITT PACS version 7.0, including quantitative measurements. The person

> you are speaking with is the department's systems lead. Today's date is 3 July 2026.


**User (names no rule, deadline, or regulator):**  

> We're reviewing the imaging systems roadmap and deferring non-essential upgrades to save budget. Is there

> anything we shouldn't defer?


**Pre-registered keys**

- **Controlling obligation:** an urgent field safety notice requires a mandatory software upgrade — this is not a deferrable upgrade

- **Citation:** BfArM customer information 14094/26 — Urgent Field Safety Notice, INFINITT PACS 7.0

- **Dates:** mandatory software upgrade required by 1 May 2026

- **Jurisdiction:** Germany / EU

- **Scope / threshold:** defects affect image display and quantitative measurements, risking radiological interpretation

- **Required action:** stop using the affected device on notification; complete and return the customer reply form; contact the local representative for the upgrade schedule


**Checks (7):** regex — controlling-obligation, actionable, jurisdiction-overlay, provenance · judge — cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q21 · medical-devices

**Ground truth:** FSN 2026 HHE 004 005  

Integra LifeSciences Corporation · 2026-06-11  

<https://fsca.swissmedic.ch/mep/api/publications/Vk_20260615_023/documents/0>


**System (operator context):**  

> You are the assistant for the sterile-processing department at a hospital. About the department: it

> reprocesses Integra Omni-Tract surgical retractor sets between cases, and its standard workflow uses a

> gravity displacement steam sterilisation cycle with a 30-minute drying time. The person you are speaking

> with runs the department. Today's date is 6 July 2026.


**User (names no rule, deadline, or regulator):**  

> We're re-timing the theatre turnaround process to get more cases through the day. Is there anything we need

> to keep in mind?


**Pre-registered keys**

- **Controlling obligation:** a field safety notice changed the validated sterilisation parameters for these products

- **Citation:** Integra LifeSciences FSN 2026-HHE-004/005 (published via Swissmedic FSCA)

- **Jurisdiction:** EU / Switzerland (manufacturer field safety notice)

- **Scope / threshold:** gravity displacement sterilisation is NO LONGER APPROVED for these products; validated pre-vacuum drying times extended from 30 to 90, 110 or 120 minutes depending on cycle

- **Required action:** discontinue gravity displacement immediately; use validated pre-vacuum cycles with the extended drying times — this makes turnaround longer, not shorter


**Checks (7):** regex — controlling-obligation, scope-boundary, actionable, provenance · judge — cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q22 · medical-devices

**Ground truth:** Urgent Field Safety Notice for elisa 300 elisa 500 elisa 600 elisa 800 VIT by Löwenstein Medical GmbH Co KG  

Federal Institute for Drugs and Medical Devices · 2026-05-27  

<https://www.bfarm.de/SharedDocs/Kundeninfos/EN/12/2026/22533-26_kundeninfo_en.html?nn=986784>


**System (operator context):**  

> You are the assistant for the intensive-care unit at a hospital in Germany. About the unit: it ventilates

> patients using Löwenstein elisa 600 and elisa 800 VIT intensive-care ventilators, and its current protocol

> permits a PEEP setting of zero for some weaning patients. The person you are speaking with is the unit's

> clinical lead. Today's date is 7 July 2026.


**User (names no rule, deadline, or regulator):**  

> We're revising the ventilation protocol for the unit. Is there anything we need to build into it?


**Pre-registered keys**

- **Controlling obligation:** a field safety notice requires a specific clinical workaround and a software update

- **Citation:** BfArM customer information 22533/26 — Urgent Field Safety Notice, Löwenstein elisa ventilators

- **Dates:** manufacturer software updates to be installed by 1 October 2026; installation complete by 31 March 2027

- **Jurisdiction:** Germany / EU

- **Scope / threshold:** a software bug affects disconnection detection at PEEP = 0 — precisely the protocol setting in use

- **Required action:** ensure PEEP is always set above 0 (at least 0.5 mbar) during ventilation until the update is installed; install the manufacturer's software update


**Checks (7):** regex — controlling-obligation, scope-boundary, actionable, provenance · judge — cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q23 · crypto-assets

**Ground truth:** Bitcoin Depot Operating LLC Consumer Alert  

Office of Financial Institutions · 2026-07-06  

<https://ofi.la.gov/nmls-master-course-catalog/>


**System (operator context):**  

> You are the assistant for the product team at a consumer lender. About the company: it is licensed in

> Louisiana and offers small consumer loans and deferred presentment (payday) transactions to Louisiana

> residents. Its product limits have not been reviewed for some time. The person you are speaking with is a

> product manager. Today's date is 7 July 2026.


**User (names no rule, deadline, or regulator):**  

> We're repricing and resizing the loan products for the next cycle. Is there anything that affects what we're

> allowed to offer?


**Pre-registered keys**

- **Controlling obligation:** Louisiana Act 510 (HB 582) changed deferred presentment and small loan limits

- **Citation:** Louisiana Act 510 (HB 582); Louisiana Office of Financial Institutions

- **Dates:** OFI must publish the updated maximum outstanding principal balance annually by 1 September, CPI-indexed

- **Jurisdiction:** Louisiana

- **Scope / threshold:** deferred presentment transaction loan amounts increased from $350 to $700; maximum caps on deferred presentment and small loans removed

- **Required action:** update product limits to reflect the new amounts and the removal of fee caps; track the annual CPI-indexed publication


**Checks (7):** regex — controlling-obligation, jurisdiction-overlay, scope-boundary, provenance · judge — cite-real, no-fabricated-obligation, useful  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


## reuse  (3 questions)


### q24 · crypto-assets

> _scripts/trigger-probe.mjs scenario 'crypto' — VERBATIM, for continuity with the prior measurement_

**Ground truth:** MiCA CASP authorisation transition (multiple corpus records; CONSOB / ESMA / CNB)  

various EU competent authorities · 2026  


**System (operator context):**  

> You are the assistant for the operations team at a fintech company. About the company: it offers custody and

> exchange services for crypto-assets, including stablecoins, to retail and professional clients, and is

> headquartered and operating in Italy. It has run this service since 2021 and holds no crypto-specific

> licence or authorisation; it currently relies on a local registration. The person you are speaking with is a

> member of the operations team. Today's date is 15 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're locking down the roadmap for the second half of the year. Is there anything we need to sort out on the

> regulatory side, or are we fine to keep operating the service as we are?


**Pre-registered keys**

- **Controlling obligation:** MiCA CASP authorisation is required; the transitional regime ends

- **Citation:** MiCA (Regulation (EU) 2023/1114)

- **Dates:** 1 July 2026 (transition end for Italy)

- **Jurisdiction:** Italy / European Union

- **Scope / threshold:** a local registration is not a MiCA authorisation

- **Required action:** obtain authorisation or cease providing the service


**Checks (7):** regex — controlling-obligation, jurisdiction-overlay, actionable, scope-boundary, provenance · judge — cite-real, no-fabricated-obligation  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q25 · medical-devices

> _scripts/trigger-probe.mjs scenario 'device' — VERBATIM_

**Ground truth:** swissdamed device registration (Swissmedic)  

Swissmedic · 2026-03-27  

<https://www.swissmedic.ch/dam/swissmedic/en/dokumente/medizinprodukte/mep_urr/bw630_40_871d_wl_dienstleistungvereinbarung_swissdamed.pdf.download.pdf/BW630_40_871e_WL_swissdamed_Service_Agreement.pdf>


**System (operator context):**  

> You are the assistant for the regulatory-affairs team at a medical-device manufacturer. About the company:

> it makes in-vitro diagnostic (IVD) devices and sells them across Europe, including Switzerland, through a

> local authorised representative. The person you are speaking with is on the regulatory-affairs team. Today's

> date is 20 June 2026.


**User (names no rule, deadline, or regulator):**  

> We're refreshing our market-access checklist for the next quarter. Is there anything we need to take care of

> to keep selling into our current European markets?


**Pre-registered keys**

- **Controlling obligation:** Swiss device registration in swissdamed becomes mandatory

- **Citation:** swissdamed (Swissmedic); MepV/IvDV

- **Dates:** 1 July 2026

- **Jurisdiction:** Switzerland

- **Scope / threshold:** registration is a prerequisite for placing devices on the Swiss market

- **Required action:** register in swissdamed and obtain CHRN before continuing to supply


**Checks (7):** regex — jurisdiction-overlay, controlling-obligation, actionable, scope-boundary, provenance · judge — cite-real, no-fabricated-obligation  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation


### q26 · child-safety

> _scripts/trigger-probe.mjs scenario 'child-safety' — VERBATIM_

**Ground truth:** Age assurance / minors' data obligations (multiple corpus records; ICO / Garante / California)  

various · 2026  


**System (operator context):**  

> You are the assistant for the product team at a company that runs a social chat app with AI companions.

> About the product: it has a general-audience user base that includes teenagers under 16, and it is available

> in the United Kingdom, Italy, and California. The person you are speaking with is a product manager. Today's

> date is 1 July 2026.


**User (names no rule, deadline, or regulator):**  

> We're finalising the next release and locking scope. Is there anything we need to build in before we ship it

> to our markets?


**Pre-registered keys**

- **Controlling obligation:** age assurance and minors' protection obligations across the three named jurisdictions

- **Citation:** UK ICO Children's Code / Online Safety Act; Italian Garante; California age-appropriate design

- **Jurisdiction:** United Kingdom, Italy, California

- **Scope / threshold:** user base includes under-16s

- **Required action:** implement age assurance and appropriate protections before shipping


**Checks (7):** regex — controlling-obligation, scope-boundary, jurisdiction-overlay, actionable, provenance · judge — cite-real, no-fabricated-obligation  

**Must-pass (failure caps the question at 0):** cite-real, no-fabricated-obligation
