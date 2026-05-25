# Demo video walkthrough brief

**Length**: 5 minutes (≈ 4:55)
**Audience**: External prospects (assume zero context about the project)
**Tone**: Third-person, calm, explanatory
**Tool**: Loom (Chrome browser extension)
**Pace**: ~140 wpm — calm. Each narration block below targets the segment duration.
**Subject**: AI-driven compliance policy review pipeline by **Carver Agents**, applied to **Mastercard SPME** publications, generating proposed updates to **Halyard Pay** (a hypothetical payment processor)

---

## 0 · Pre-flight checklist (one-time, ~2 min)

```
1. cd <repo>/credio-policies/dist
2. python3 -m http.server 8080      # leave this terminal open
```

In Chrome:
1. **New Incognito window** (`⌘⇧N`) — keeps bookmarks bar and extensions out of frame.
2. **Hide bookmarks bar** (`⌘⇧B`) if visible.
3. **Set window size to 1440×900** — use a window-resize extension or drag manually.
4. Confirm the Loom extension icon is in the top right.
5. Open `http://localhost:8080/index.html`. Wait for fonts to load (the "Halyard Pay · Policy Updates" header should be in Poppins, not the system serif).
6. Loom settings: **Screen + Camera**, **HD 1080p**, camera bubble in bottom-right or off.
7. Click **Start recording**.

---

## 1 · Glossary (pronunciation guide)

| Term | Pronounce as | Notes |
|---|---|---|
| Halyard Pay | HAL-yard pay | The hypothetical payment processor (made-up, not a real brand) |
| SPME | "S-P-M-E" (initialism) | Mastercard's Security Rules and Procedures, Merchant Edition |
| BRAM | "bram" (rhymes with jam) | Business Risk Assessment and Mitigation |
| ECP | "E-C-P" | Excessive Chargeback Program |
| KYB | "K-Y-B" | Know Your Business |
| MATCH | "match" (word) | Member Alert to Control High-risk Merchants |
| Acquirer | "uh-KWIRE-er" | The institution that processes for merchants |
| Materiality | "muh-TEER-ee-al-it-ee" | Severity grade (breaking → cosmetic) |
| Carver Agents | "CAR-ver" | The agent platform brand |

---

## 2 · Storyboard

> Every section gives: **URL**, **timing**, **on-screen action**, **narration script (read verbatim)**.
> Quoted narration is sized to fit the target duration at ~140 wpm; pause briefly between paragraphs.

---

### Segment 1 — Overview page · 0:00 → 1:00 (60s)

**URL**: `http://localhost:8080/index.html`

**Pre-state**: scrolled to top.

**Camera actions**:

| Cue | Action | Duration |
|---|---|---|
| 0:00 | Hold on hero (title + lede + 4-up stats). | 12s |
| 0:12 | Slow smooth-scroll to the **"01 · How it works"** three-step section. Pause on it. | 18s |
| 0:30 | Continue scrolling slowly to **"02 · Inputs"** — show the list of 6 Mastercard PDF links. | 12s |
| 0:42 | Continue scrolling to **"03 · Outputs"** — show the 8 policy mini-cards. | 8s |
| 0:50 | Scroll to **"04 · Vocabulary"** — pause specifically on the materiality grades (the four colored chips at the bottom of the glossary). | 10s |

**Narration**:

> "This is an AI-generated review of how Mastercard's Security Rules and Procedures publication — abbreviated S-P-M-E — has evolved across five releases between 2022 and 2025. The agent reads each successive version of the publication, identifies every section that changed, classifies the severity of each change, and proposes corresponding updates to the internal policies of Halyard Pay — a hypothetical payment processor used here to demonstrate the workflow. The source documents are public Mastercard publications, archived via the Internet Archive Wayback Machine. They're bundled with this demo so reviewers can verify every proposal directly against the source. Halyard Pay's policies shown here are synthetic baselines — not real production text. The pipeline runs three stages: detect, classify, propose. Each change gets a materiality grade — breaking, substantive, clarifying, or cosmetic — depending on whether it alters a real compliance obligation."

---

### Segment 2 — Timeline page · 1:00 → 1:30 (30s)

**Click**: **Timeline** in the top nav (or click "Begin review →").

**URL after click**: `http://localhost:8080/timeline/index.html`

**Camera actions**:

| Cue | Action | Duration |
|---|---|---|
| 1:00 | Land at top of timeline page, hold. | 6s |
| 1:06 | Slow scroll down to bring all 5 release cards into view. | 12s |
| 1:18 | Hover briefly over the colored severity bar on a card with multiple grades (the Jun 2022 → May 2023 card has the most variety). | 12s |

**Narration**:

> "The timeline view shows all five Mastercard S-P-M-E release transitions in chronological order. Each row shows the date range, how many revisions were proposed in that release, and a colored severity bar showing the materiality breakdown. Across the full timeline, the agent flagged 15 changes as breaking and 199 as substantive, affecting all eight Halyard Pay policy areas."

---

### Segment 3 — One transition page + PDF deep-link · 1:30 → 2:30 (60s)

**Click**: the **Sep 2024 → May 2025** card.

**URL after click**: `http://localhost:8080/transitions/2024-09_to_2025-05.html`

**Camera actions**:

| Cue | Action | Duration |
|---|---|---|
| 1:30 | Land at top. Show breadcrumb, H1, lede. Hold. | 6s |
| 1:36 | Hover over (don't click) the **Search box** and filter chips, briefly demonstrating the filter affordance. | 10s |
| 1:46 | Scroll down past the filter into the grouped change cards. | 6s |
| 1:52 | Click into the **§6.2.2 Acquirer Fraud Loss Control Programs** change card. | (transition) |
| 1:53 | Land on the change-detail page. Hold on the header + sources row. | 6s |
| 1:59 | Click the **"Mastercard SPME · Sep 2024 · page 60 ↗"** link in the sources row. New tab opens at the PDF page. | 6s |
| 2:05 | In the PDF: confirm the section 6.2.2 is at the top of page 60. Hold ~4s. | 4s |
| 2:09 | Close the PDF tab. Back on the change page. Scroll to the **Side-by-side** tab content. | 8s |
| 2:17 | Click the **"Raw diff"** tab to show the unified diff. | 6s |
| 2:23 | Click back to **"Side-by-side"**. Hold. | 7s |

**Narration**:

> "Drilling into one release — September 2024 to May 2025 — every detected change appears as a card, grouped by materiality with breaking changes first. A search box and filter pills let reviewers narrow by section ID, policy, or severity. Each card cites the specific S-P-M-E section number and lists the affected Halyard Pay policies.
>
> Clicking into a change opens the detail page. The Sources row at the top links directly to both Mastercard PDFs — and crucially, with a page-number anchor that opens the source document at the exact page where the cited section appears. One click and the reviewer is staring at the original Mastercard text.
>
> The Side-by-side tab shows the original S-P-M-E section on the left with word-level redlines, and the proposed Halyard Pay policy edits on the right. The Raw diff tab provides the underlying unified diff for engineers, while the Redline tab renders the proposed policy as the document will read after the change is accepted."

---

### Segment 4 — Two verified change pages · 2:30 → 4:00 (90s)

#### 4a. Sample 2 — §7.2 Ongoing Monitoring (2023-05 → 2023-09) · 2:30 → 3:15 (45s)

**Direct URL**: `http://localhost:8080/changes/2023-05_to_2023-09_7.2.html`

(Easiest to type into the URL bar, or navigate Timeline → May 2023 release → §7.2 card.)

**Camera actions**:

| Cue | Action | Duration |
|---|---|---|
| 2:30 | Land at top of change page. Show breadcrumb + title + materiality badge. Hold. | 6s |
| 2:36 | Highlight the "Why these edits?" callout. Hold long enough to read. | 8s |
| 2:44 | Scroll down to the Side-by-side compare. Show the SPME redline on the left and the YAML/markdown diff on the right. | 14s |
| 2:58 | Click **Redline** tab. Show the proposed updated policy with inline green additions / red strikethroughs. | 12s |
| 3:10 | Click back to **Side-by-side**. Hold for ~5s. | 5s |

**Narration**:

> "This is a verified example — section 7.2, Ongoing Monitoring, in the May to September 2023 release. The agent's summary states that Mastercard added new obligations: acquirers must regularly review e-commerce merchants' websites and verify their business activities. The 'Why these edits?' callout at the top explains the reasoning in plain English. Clicking through to the source PDF confirms the new language word-for-word. The pipeline proposes adding the new requirement to Halyard Pay's Fraud Monitoring policy. The Redline tab shows what the policy will read like after the change is accepted — same content as the side-by-side, but laid out as a track-changes document for compliance review."

---

#### 4b. Sample 3 — §2.2.3 Service Provider Compliance (2024-02 → 2024-09) · 3:15 → 4:00 (45s)

**Direct URL**: `http://localhost:8080/changes/2024-02_to_2024-09_2.2.3.html`

**Camera actions**:

| Cue | Action | Duration |
|---|---|---|
| 3:15 | Land at top. Show title + materiality + summary. Hold. | 8s |
| 3:23 | Scroll to the Side-by-side. The right column shows the **rules.yaml** diff — point out the **`compliance_cadence: biennial`** value change from `annual`. | 18s |
| 3:41 | Hover over the **KYB Acquirer · rules.yaml** chip in the right column (this is a link to the policy detail page). Briefly mention the cross-link. | 7s |
| 3:48 | Click into the **KYB Acquirer** policy detail page. Land on the policy page, show its current text + the mini-timeline of all changes affecting it. | 12s |

**Narration**:

> "A second verified example — section 2.2.3, Service Provider Compliance Requirements, between February and September 2024. Here, Mastercard relaxed a compliance cadence: 3-D-S Service Provider validation is now required every two years instead of annually. The pipeline picked up the threshold shift and proposed updating the validation interval in the K-Y-B Acquirer policy's rules.yaml — a concrete, machine-readable value change.
>
> Every affected policy file in this view is a live link. Clicking through opens the policy detail page, which shows the current policy text plus a mini-timeline of every proposed change touching it across all five releases — useful for spotting any policy that's been repeatedly revised."

---

### Segment 5 — Low-confidence change with extraction warning · 4:00 → 4:30 (30s)

**Direct URL**: `http://localhost:8080/changes/2022-06_to_2023-05_8.6.5.html`

**Camera actions**:

| Cue | Action | Duration |
|---|---|---|
| 4:00 | Land at top of the §8.6.5 page. The **yellow extraction-warning callout** is immediately under the title. Hold on it. | 10s |
| 4:10 | Click the **"May 2023 · page 92 ↗"** link in the warning to open the source PDF in a new tab. | 4s |
| 4:14 | Show the PDF: §8.6.5 is on page 92, but its body text was attributed to the next section. Close the tab. | 8s |
| 4:22 | Back on the change page. Briefly scroll down to show the (incorrectly-attributed) side-by-side. | 8s |

**Narration**:

> "Not every AI-generated proposal is trustworthy — and that's important to surface honestly. The pipeline self-detects suspicious extractions and flags them. Section 8.6.5, Chargeback Responsibility. The yellow warning at the top calls out that the source PDF appears to have a section-boundary issue — a page running-header confused the boundary detector, and the body text from another section bled in. Out of 214 change records, 22 were flagged this way. Reviewers see the doubt before reading the AI's claim, and can verify against the source PDF in one click."

---

### Closing card · 4:30 → 4:55 (~25s)

Navigate back to **Overview** (click Overview in nav, or `http://localhost:8080/index.html`). Scroll back to the top — show the 4-up stats strip.

**Narration**:

> "Five Mastercard releases reviewed. 214 changes detected. Eight policy areas evaluated. 22 changes flagged for human verification. This is what an AI compliance agent looks like when it's transparent about what it knows, what it proposes, and what it might have gotten wrong. Built by Carver Agents."

End recording.

---

## 3 · Recording tips

- **Move slowly.** Cursor speed should be ~half of natural. The audience needs time to parse each screen.
- **Pause on transitions.** Wait 1 sec after every page load before starting to narrate the new section.
- **Avoid scroll-jitter.** Use trackpad two-finger scroll, smooth, not the scrollbar.
- **One take is fine.** If you flub a line, just keep going — Loom lets you trim. Don't aim for perfection.
- **No mouse circles** to highlight things — use deliberate cursor parking near the element you're narrating about.
- **Test the PDF deep-link first** (Segment 3). Some Chrome installs download PDFs instead of inline-previewing; if yours does, change Chrome's PDF setting under `chrome://settings/content/pdfDocuments` before recording.

## 4 · After recording

- Trim head and tail; aim for ≤ 5:00 final.
- Keep camera bubble (or remove if it's distracting).
- Export 1080p, mp4 (Loom does this by default).
- File name suggestion: `halyard-pay-spme-demo-v1.mp4`.

## 5 · Reference: silent walkthrough video

A silent reference recording of the same flow exists at `dist/demo-reference.webm` (produced by `scripts/record_demo.py`). Use it to time your narration if helpful — it follows this brief exactly.
