# Spec: α — Regulatory Risk Radar

> **Status:** Draft, pending team review.
> **Strategy doc reference:** § 4.1.
> **Prerequisites:** [`10-data-spine.md`](10-data-spine.md) fully implemented.

α answers the question: **"Did a regulator just do something that affects *us* (this platform)?"** It turns matched spine events into a tickets workflow for the GC / CCO team.

---

## 1. Purpose & Buyer

- **Buyer of record:** General Counsel / Chief Compliance Officer at the prediction-market platform.
- **Primary users:** GC, CCO, junior counsel.
- **Procurement:** legal / compliance budget.
- **Replaces:** Google Alerts, Twitter, journalist tips, law-firm panels, ad-hoc spreadsheets.

---

## 2. In Scope / Out of Scope

**In scope:**
- Triage queue (tickets) auto-created from filter matches on "triage-enabled" filters.
- Ticket lifecycle: statuses, comments, assignees, due dates.
- Multi-channel alerts (real-time and digest) keyed off user preferences.
- Per-jurisdiction dashboard (US states + federal + international × update_type × time).
- Audit-log export (PDF + CSV).
- α-specific user preferences (urgency threshold, digest cadence, channels).

**Out of scope (V1):**
- Cross-tenant ticket sharing or escalation.
- Automated counsel-response drafting (that's δ, not α).
- ε-grade per-contract audit dossier (γ owns contract-touching events; ε is roadmap).
- Settlement / oracle workflows.

---

## 3. Data Model (α-specific)

All tables are tenant-scoped (RLS pattern from data-spine spec § 4).

### 3.1 Tickets

```sql
CREATE TABLE tickets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    filter_match_id     UUID NOT NULL REFERENCES filter_matches(id),
    event_id            UUID NOT NULL REFERENCES regulatory_events(id),
    saved_filter_id     UUID NOT NULL REFERENCES saved_filters(id),
    status              TEXT NOT NULL CHECK (status IN (
        'new','acknowledged','in_review','drafted','escalated','closed'
    )),
    priority            INT NOT NULL CHECK (priority BETWEEN 1 AND 10),
    assigned_to         UUID REFERENCES users(id),
    due_date            DATE,
    closed_at           TIMESTAMPTZ,
    closed_reason       TEXT CHECK (closed_reason IN (
        'resolved','no_action','duplicate','false_positive'
    )),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (filter_match_id)
);

CREATE INDEX tickets_tenant_status_priority_idx ON tickets(tenant_id, status, priority DESC, created_at DESC);
CREATE INDEX tickets_assigned_idx                ON tickets(tenant_id, assigned_to) WHERE status != 'closed';
CREATE INDEX tickets_due_idx                     ON tickets(tenant_id, due_date) WHERE status != 'closed';

ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
CREATE POLICY tickets_tenant_isolation ON tickets
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

**Priority derivation** (at ticket creation, denormalized for fast sort):
```python
priority = round((event.urgency_score * 0.6) + (event.impact_score * 0.4))
priority = max(1, min(10, priority))
```

**Due-date derivation:**
```python
# Precedence: comment_deadline > compliance_date > effective_date
due_date = event.comment_deadline or event.compliance_date or event.effective_date
```

### 3.2 Status transitions

```sql
CREATE TABLE ticket_status_transitions (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    ticket_id           UUID NOT NULL REFERENCES tickets(id),
    from_status         TEXT,
    to_status           TEXT NOT NULL,
    transitioned_by     UUID REFERENCES users(id),
    actor_kind          TEXT NOT NULL CHECK (actor_kind IN ('user','system')),
    note                TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ticket_status_transitions_ticket_idx ON ticket_status_transitions(ticket_id, created_at);
ALTER TABLE ticket_status_transitions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tst_tenant_isolation ON ticket_status_transitions
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

Valid transitions:

```
              ┌──→ acknowledged ──→ in_review ──→ drafted ──→ closed
   new ───┤                                    └──→ escalated ──→ closed
              └──→ closed (false_positive | no_action shortcut)
```

The transition graph is enforced in code; rejected transitions return `409 Conflict`.

### 3.3 Comments

```sql
CREATE TABLE ticket_comments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    ticket_id           UUID NOT NULL REFERENCES tickets(id),
    author_id           UUID NOT NULL REFERENCES users(id),
    body                TEXT NOT NULL,
    mentioned_user_ids  UUID[] NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ticket_comments_ticket_idx ON ticket_comments(ticket_id, created_at);
ALTER TABLE ticket_comments ENABLE ROW LEVEL SECURITY;
CREATE POLICY ticket_comments_tenant_isolation ON ticket_comments
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

Mentions of the form `@user@example.com` are parsed at write time and stored in `mentioned_user_ids` for cheap notification fan-out.

### 3.4 User preferences (α-specific)

```sql
CREATE TABLE alpha_user_preferences (
    user_id                 UUID PRIMARY KEY REFERENCES users(id),
    tenant_id               UUID NOT NULL REFERENCES tenants(id),
    page_urgency_threshold  INT NOT NULL DEFAULT 8 CHECK (page_urgency_threshold BETWEEN 1 AND 10),
    digest_cadence          TEXT NOT NULL DEFAULT 'daily' CHECK (digest_cadence IN ('off','daily','weekly')),
    digest_min_priority     INT NOT NULL DEFAULT 5,
    digest_time_utc         TIME NOT NULL DEFAULT '14:00',     -- 9am ET
    digest_day_of_week      INT CHECK (digest_day_of_week BETWEEN 0 AND 6),  -- 0 = Monday; used when digest_cadence='weekly'
    channels                TEXT[] NOT NULL DEFAULT '{email}',  -- subset of: 'slack','email','sms'
    assigned_to_me_only     BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE alpha_user_preferences ENABLE ROW LEVEL SECURITY;
CREATE POLICY aup_tenant_isolation ON alpha_user_preferences
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

---

## 4. Ticket-Creation Flow

Triggered when `filter_matches` row is INSERTed for a saved filter where `is_triage_source = TRUE`. This adds a new boolean to `saved_filters`:

```sql
ALTER TABLE saved_filters ADD COLUMN is_triage_source BOOLEAN NOT NULL DEFAULT FALSE;
```

(Spine spec § 7.4 already defines `is_alert_source`; α adds `is_triage_source`. A filter can be either, both, or neither.)

ARQ job `alpha.create_ticket_for_match(filter_match_id)`:

1. Load `filter_matches`, `saved_filters`, `regulatory_events`.
2. Compute `priority` and `due_date` per § 3.1.
3. INSERT into `tickets` (UNIQUE on `filter_match_id` guarantees idempotency).
4. INSERT into `ticket_status_transitions` (`from_status=NULL`, `to_status='new'`, `actor_kind='system'`).
5. Enqueue `alpha.dispatch_new_ticket_alerts(ticket_id)`.

`alpha.dispatch_new_ticket_alerts(ticket_id)`:
1. Load ticket + event + tenant.
2. For each `alpha_user_preferences` row in the tenant where:
   - `digest_cadence != 'off'`, and
   - `event.urgency_score >= page_urgency_threshold` (this is a real-time page candidate)
3. Enqueue a `notification_dispatches` row per (user × channel) and trigger the spine's notification dispatcher.

Real-time pages skip the digest queue. Lower-priority events accumulate for digest dispatch (§ 6.2).

---

## 5. APIs

All under `/api/v1/alpha`. Auth and tenant context inherited from spine middleware.

| Endpoint | Method | Role | Purpose |
|---|---|---|---|
| `/api/v1/alpha/tickets` | GET | any | List tickets. Query params: `status`, `assigned_to`, `priority_min`, `jurisdiction`, `q` (text), `page`, `page_size`. Returns paginated DTOs. |
| `/api/v1/alpha/tickets/{id}` | GET | any | Ticket detail + event payload + transitions + comments. |
| `/api/v1/alpha/tickets/{id}/transition` | POST | triager+ | Body: `{"to_status": "...", "note": "...", "closed_reason": "..."}`. Validates graph; writes transition; updates `tickets.status`. |
| `/api/v1/alpha/tickets/{id}/assign` | POST | triager+ | Body: `{"user_id": "..."}`. Idempotent. |
| `/api/v1/alpha/tickets/{id}/comments` | POST | triager+ | Body: `{"body": "..."}`. Parses mentions; notifies mentioned users. |
| `/api/v1/alpha/tickets/{id}/comments` | GET | any | List comments. |
| `/api/v1/alpha/dashboard/jurisdictions` | GET | any | Returns 2D grid: jurisdiction × update_type, counts in window. Query: `from`, `to`, `tier`. |
| `/api/v1/alpha/dashboard/jurisdictions/{code}/events` | GET | any | Drilldown: events for jurisdiction in window. |
| `/api/v1/alpha/preferences` | GET, PATCH | self | User's α preferences. |
| `/api/v1/alpha/audit-export` | POST | admin | Body: `{"from": "...", "to": "...", "format": "csv"|"pdf"}`. Returns 202 with a job_id; result fetched via `/api/v1/alpha/audit-export/{job_id}`. Generates audit-log slice (ticket events) and signed download URL valid 24h. |

### 5.1 Ticket DTO shape

```jsonc
{
  "id": "uuid",
  "status": "new|acknowledged|in_review|drafted|escalated|closed",
  "priority": 1-10,
  "assigned_to": { "id": "uuid", "display_name": "...", "email": "..." } | null,
  "due_date": "YYYY-MM-DD" | null,
  "closed_at": "ISO" | null,
  "closed_reason": "..." | null,
  "filter": { "id": "uuid", "name": "..." },
  "event": {
    "id": "uuid",
    "title": "...",
    "summary": "...",
    "feed_url": "...",
    "pub_date": "YYYY-MM-DD",
    "update_type": "...",
    "regulatory_source_name": "...",
    "jurisdictions": ["..."],
    "urgency_score": 0-10,
    "impact_score": 0-10,
    "effective_date": "..." | null,
    "comment_deadline": "..." | null
  },
  "created_at": "ISO",
  "updated_at": "ISO"
}
```

---

## 6. Background Jobs

| Job | Schedule | Purpose |
|---|---|---|
| `alpha.create_ticket_for_match` | event-triggered | (§ 4) |
| `alpha.dispatch_new_ticket_alerts` | event-triggered | (§ 4) |
| `alpha.send_daily_digest` | cron, hourly @ :00 | For each (tenant, user) where `digest_cadence='daily'` and `digest_time_utc == current_hour`, gather tickets `created_at >= now() - 24h` with `priority >= user.digest_min_priority` and dispatch a digest email. |
| `alpha.send_weekly_digest` | cron, hourly @ :00 | Same, weekly cadence, with `digest_day_of_week == current_dow`. |
| `alpha.escalate_overdue_tickets` | cron, daily @ 09:00 UTC | Tickets with `status NOT IN ('closed')` AND `due_date < today()`: post a Slack notice to the tenant's default channel and mark a `priority := min(10, priority + 1)` bump. Records `ticket_status_transitions` with `actor_kind='system'` even if status unchanged (audit trail). |

### 6.1 Real-time alert message

Slack Block Kit, channel `alpha.alert.slack.j2`. Example rendered text:

```
🚨 Urgency 9 / Impact 8 — α match
Title: CFTC Issues Cease and Desist Against [Tenant Name]
Source: CFTC Division of Enforcement
Effective: 2026-06-01
Filter: "Direct enforcement against us"
Open ticket → https://app.predoracle.example/alpha/tickets/<id>
Primary source → https://www.cftc.gov/...
```

### 6.2 Digest message

Email template `alpha.digest.email.j2`. Top of body:

```
Pred-Oracle daily digest — 2026-05-19
12 new tickets above your priority threshold (5).
   3 high (priority 8+)
   5 medium (priority 6–7)
   4 low  (priority 5)
[ table of tickets: priority | title | source | jurisdictions | open link ]
```

---

## 7. UI Surfaces

### 7.1 Inbox (triage queue)

Route: `/alpha/inbox`.

Header controls:
- **Status filter chips:** New / Acknowledged / In Review / Drafted / Escalated / Closed (multi-select).
- **Assignee dropdown:** All / Me / specific user.
- **Priority range slider:** 1–10.
- **Jurisdiction filter:** multi-select from tenant's `jurisdictional_footprint`.
- **Free-text search:** matches `title`, `summary`, `regulatory_source_name`, `entities`.

Body: paginated table, default sort `status='new' first, then priority DESC, created_at DESC`. Columns:
- Priority badge (color-coded)
- Title (clickable → detail)
- Source agency
- Jurisdictions (chips)
- Status badge
- Assignee avatar
- Due date (red if past)
- Created (relative time)

Row click → `/alpha/tickets/{id}`.

### 7.2 Ticket detail

Route: `/alpha/tickets/{id}`.

Layout:
- **Left pane (60%):** event details — title, source, dates, all Carver fields rendered cleanly. Linked primary source. "Impact summary" and "Penalties & consequences" rendered as cards.
- **Right pane (40%):**
  - Workflow controls: status dropdown (valid transitions only), assignee, due-date editor.
  - Status history (vertical timeline of `ticket_status_transitions`).
  - Comment thread (`ticket_comments`) with markdown rendering, @mention autocomplete.

### 7.3 Per-jurisdiction dashboard

Route: `/alpha/dashboard`.

Heat-map grid:
- **Rows:** jurisdictions (US federal, 50 US states, top-N international from tenant's footprint), grouped by tier.
- **Columns:** update_type (enforcement, final rule, proposed rule, guidance, advisory, …).
- **Cell:** count of events in the selected date window; intensity = log(count). Click → drilldown list.

Controls:
- Date window: last 30d (default), 90d, 365d, custom.
- Tier filter: US federal / US state / international / all.
- Update-type filter.

Drilldown panel (slide-in from right): event list for selected cell, click-through to either ticket (if α-flagged) or a read-only event detail.

### 7.4 Audit export

Route: `/alpha/audit-export`.

Form:
- Date range pickers.
- Format radio: PDF (formatted report) / CSV (raw rows).
- "Include events" checkbox (joins event payload to each ticket).
- Generate button → POST API, polls every 3s, downloads when ready.

PDF template `alpha.audit_export.pdf.j2` rendered via WeasyPrint, with tenant logo header, date range, and a row per (ticket, transition) ordered chronologically. CSV is one row per transition with denormalized event metadata.

### 7.5 α preferences (within user settings)

Route: `/settings/alpha`.

Form: `page_urgency_threshold` slider, `digest_cadence` radio, `digest_min_priority` slider, `digest_time_utc` + `digest_day_of_week` pickers, `channels` checkboxes, `assigned_to_me_only` toggle.

---

## 8. Integrations

α reuses the spine's notification dispatcher (§ 8 of data-spine spec). No new outbound integrations.

Inbound: optional webhook from customer's GRC/Jira systems to acknowledge ticket creation back into Pred-Oracle (V1.x — out of scope for first ship).

---

## 9. Acceptance Criteria

α GA (M6 milestone) requires:

- [ ] Tenant admin creates a saved filter with `is_triage_source = TRUE`; matching event → ticket within 60s p95.
- [ ] Real-time Slack alert fires for an event with `urgency_score >= user.page_urgency_threshold`, delivered <5s after ticket creation.
- [ ] Daily digest email fires at user's configured `digest_time_utc`, listing tickets above threshold within last 24h. Property test: 100 simulated users × 7 days delivers expected digests.
- [ ] Weekly digest equivalent.
- [ ] Ticket lifecycle: every valid status transition (per § 3.2 graph) is allowed; every invalid one is rejected `409`.
- [ ] Comment thread with @mentions: mentioned user receives a notification per their channel preferences.
- [ ] Per-jurisdiction dashboard: counts agree with a hand-computed SQL query within ±1 (rounding tolerance) over a fixture dataset.
- [ ] Audit export PDF includes every transition for tickets in the date window; CSV equivalent. Sample export reviewed by a real GC (design partner).
- [ ] Overdue-ticket escalation cron: ticket with `due_date < today` triggers a Slack post and priority bump.
- [ ] RLS verified: tenant A's user cannot list, read, or transition tenant B's tickets (integration test).
- [ ] North-star metric instrumented: `triaged_updates_per_tenant_per_week` rolling 7-day count exported to ops dashboard.

---

## 10. Open Questions (α-local)

| # | Question | Suggested resolution |
|---|---|---|
| A1 | Is the status graph (§ 3.2) actually right for how GCs work? | Validate with both design-partner GCs in design-partner kickoff. Likely needs an `awaiting_external_counsel` state for outside law-firm collaboration; add as M5 enhancement. |
| A2 | Should there be a "snooze ticket until X" capability? | Yes; cheap to add (`snooze_until TIMESTAMPTZ` column, filtered out of default inbox view). Include in V1.0. |
| A3 | Bulk operations (bulk close, bulk assign) — needed for V1? | Yes for closing; not for assigning. Implement bulk close as a v1 endpoint with confirmation modal. |
| A4 | Per-state US drilldown — needed for V1? | Yes for the 10 states with active Kalshi enforcement (per strategy doc § 2.1). Render as a separate "US state radar" tab in the dashboard with all 50 states. |
| A5 | Are urgency / impact scores stable enough from Carver to drive paging? | Sample 100 events from a representative month, have a GC label "should this page?" — calibrate the threshold default if needed. Resolve at M4. |
| A6 | What happens when an event is re-ingested with updated scores (Carver correction)? | Update the `event` row; if a ticket already exists for the filter_match, leave the ticket but write a `ticket_status_transitions` row noting the score change, and re-evaluate page-threshold for any not-yet-acknowledged ticket. |
