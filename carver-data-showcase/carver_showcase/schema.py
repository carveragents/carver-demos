"""Normalized column contract for the Carver Annotation Data Showcase.

Logic-free: this module declares only the column list, dtypes, and the
extraction map (nested source path → column name). No functions, no I/O.

FIELD_MAP uses probe-confirmed source paths (see implementation spec).
"""

# ---------------------------------------------------------------------------
# NORMALIZED_COLUMNS — the complete ordered column set (spec §4.2)
# ---------------------------------------------------------------------------

NORMALIZED_COLUMNS: list[str] = [
    # --- Identity / envelope ---
    "artifact_id",
    "entry_id",
    "topic_id",
    "source_id",
    "state",
    "artifact_created_at",
    "artifact_updated_at",
    # --- Scores: impact ---
    "impact_label",
    "impact_score",
    "impact_confidence",
    # --- Scores: urgency ---
    "urgency_label",
    "urgency_score",
    "urgency_confidence",
    "urgency_basis",
    # --- Scores: relevance ---
    "relevance_label",
    "relevance_score",
    "relevance_confidence",
    # --- Classification ---
    "update_type",
    "update_subtype",
    "regulator_name",
    "regulator_division",
    "regulator_other_agency",
    "jurisdiction_scope",
    "jurisdiction_country",
    "jurisdiction_bloc",
    "jurisdiction_locality",
    "jurisdiction_region",
    "jurisdiction_reasoning",
    "has_jurisdiction_tier_legacy",
    # --- Category (catalog-sourced, joined on topic_id) ---
    "category",
    # --- Source document ---
    "title",
    "feed_url",
    "base_url",
    "language",
    "source_type",
    "summary",
    # --- Key dates + paired *_calendar ---
    "effective_date",
    "effective_date_calendar",
    "compliance_date",
    "compliance_date_calendar",
    "comment_deadline",
    "comment_deadline_calendar",
    "early_adoption_date",
    "early_adoption_date_calendar",
    "updated_date",
    "updated_date_calendar",
    "pub_date_content",
    "pub_date_calendar",
    "n_other_dates",
    # --- Reconciled published date + provenance ---
    "reconciled_published_date",
    "reconciled_pub_source",
    "reconciled_pub_converted",
    "reconciled_pub_original_calendar",
    "reconciled_pub_valid",
    # --- Richness counts & flags ---
    "n_tags",
    "n_entities",
    "n_actionable_lanes",
    "has_impact_summary",
    "has_objective",
    "has_what_changed",
    "has_why_it_matters",
    "has_risk_impact",
    "n_key_requirements",
    "n_reg_rules",
    "n_reg_statutes",
    "n_reg_other_ref",
    "n_reg_personnel",
    "n_reg_precedents",
    "n_reg_past_release",
    "n_reg_refs_total",
    "has_impacted_business",
    "n_impacted_functions",
    "n_penalties",
    "has_penalties",
    "n_critical_dates",
    "richness_score",
    # --- Quality support columns (Phase 4) ---
    "min_prose_len",
    "n_unparseable_dates",
]

# ---------------------------------------------------------------------------
# DTYPES — column → pandas dtype (used when building/reading the parquet)
# ---------------------------------------------------------------------------

DTYPES: dict[str, str] = {
    # Identity
    "artifact_id": "string",
    "entry_id": "string",
    "topic_id": "string",
    "source_id": "string",
    "state": "string",
    "artifact_created_at": "datetime64[ns, UTC]",
    "artifact_updated_at": "datetime64[ns, UTC]",
    # Scores
    "impact_label": "string",
    "impact_score": "Float64",
    "impact_confidence": "Float64",
    "urgency_label": "string",
    "urgency_score": "Float64",
    "urgency_confidence": "Float64",
    "urgency_basis": "string",
    "relevance_label": "string",
    "relevance_score": "Float64",
    "relevance_confidence": "Float64",
    # Classification
    "update_type": "string",
    "update_subtype": "string",
    "regulator_name": "string",
    "regulator_division": "string",
    "regulator_other_agency": "string",
    "jurisdiction_scope": "string",
    "jurisdiction_country": "string",
    "jurisdiction_bloc": "string",
    "jurisdiction_locality": "string",
    "jurisdiction_region": "string",
    "jurisdiction_reasoning": "string",
    "has_jurisdiction_tier_legacy": "boolean",
    # Category
    "category": "string",
    # Source
    "title": "string",
    "feed_url": "string",
    "base_url": "string",
    "language": "string",
    "source_type": "string",
    "summary": "string",
    # Key dates
    "effective_date": "string",
    "effective_date_calendar": "string",
    "compliance_date": "string",
    "compliance_date_calendar": "string",
    "comment_deadline": "string",
    "comment_deadline_calendar": "string",
    "early_adoption_date": "string",
    "early_adoption_date_calendar": "string",
    "updated_date": "string",
    "updated_date_calendar": "string",
    "pub_date_content": "string",
    "pub_date_calendar": "string",
    "n_other_dates": "Int64",
    # Reconciled date
    "reconciled_published_date": "datetime64[ns, UTC]",
    "reconciled_pub_source": "string",
    "reconciled_pub_converted": "boolean",
    "reconciled_pub_original_calendar": "string",
    "reconciled_pub_valid": "boolean",
    # Richness
    "n_tags": "Int64",
    "n_entities": "Int64",
    "n_actionable_lanes": "Int64",
    "has_impact_summary": "boolean",
    "has_objective": "boolean",
    "has_what_changed": "boolean",
    "has_why_it_matters": "boolean",
    "has_risk_impact": "boolean",
    "n_key_requirements": "Int64",
    "n_reg_rules": "Int64",
    "n_reg_statutes": "Int64",
    "n_reg_other_ref": "Int64",
    "n_reg_personnel": "Int64",
    "n_reg_precedents": "Int64",
    "n_reg_past_release": "Int64",
    "n_reg_refs_total": "Int64",
    "has_impacted_business": "boolean",
    "n_impacted_functions": "Int64",
    "n_penalties": "Int64",
    "has_penalties": "boolean",
    "n_critical_dates": "Int64",
    "richness_score": "Float64",
    # Quality support columns
    "min_prose_len": "Int64",
    "n_unparseable_dates": "Int64",
}

# ---------------------------------------------------------------------------
# FIELD_MAP — probe-confirmed source path → column name
#
# Keys are dotted path strings into the raw envelope/output_data/input_data.
# Values are the destination column names (must be in NORMALIZED_COLUMNS).
#
# Paths confirmed against live payload sample (spec implementation note).
# Computed/derived columns (richness counts, flags, base_url, category) are
# NOT in FIELD_MAP — they are produced by normalize.py logic.
# ---------------------------------------------------------------------------

FIELD_MAP: dict[str, str] = {
    # --- Envelope ---
    "id": "artifact_id",
    "topic_id": "topic_id",
    "source_id": "source_id",
    "state": "state",
    "created_at": "artifact_created_at",
    "completed_at": "artifact_updated_at",
    # --- output_data top-level ---
    "output_data.entry_id": "entry_id",
    # --- Scores ---
    "output_data.scores.impact.label": "impact_label",
    "output_data.scores.impact.score": "impact_score",
    "output_data.scores.impact.confidence": "impact_confidence",
    "output_data.scores.urgency.label": "urgency_label",
    "output_data.scores.urgency.score": "urgency_score",
    "output_data.scores.urgency.confidence": "urgency_confidence",
    "output_data.scores.urgency.basis": "urgency_basis",
    "output_data.scores.relevance.label": "relevance_label",
    "output_data.scores.relevance.score": "relevance_score",
    "output_data.scores.relevance.confidence": "relevance_confidence",
    # --- Classification ---
    "output_data.classification.update_type": "update_type",
    "output_data.classification.update_subtype": "update_subtype",
    "output_data.classification.regulatory_source.name": "regulator_name",
    "output_data.classification.regulatory_source.division_office": "regulator_division",
    "output_data.classification.regulatory_source.other_agency": "regulator_other_agency",
    "output_data.classification.jurisdiction.scope": "jurisdiction_scope",
    "output_data.classification.jurisdiction.country": "jurisdiction_country",
    "output_data.classification.jurisdiction.bloc": "jurisdiction_bloc",
    "output_data.classification.jurisdiction.locality": "jurisdiction_locality",
    "output_data.classification.jurisdiction.region_name": "jurisdiction_region",
    "output_data.classification.jurisdiction.reasoning": "jurisdiction_reasoning",
    # --- Source document (title/feed_url/summary/language from classification.metadata per probe) ---
    "output_data.classification.metadata.title": "title",
    "output_data.classification.metadata.feed_url": "feed_url",
    "output_data.classification.metadata.language": "language",
    "output_data.classification.metadata.summary": "summary",
    # --- Source metadata from input_data ---
    "input_data.extracted_metadata.source_type": "source_type",
    # --- Key dates ---
    "output_data.metadata.critical_dates.effective_date": "effective_date",
    "output_data.metadata.critical_dates.effective_date_calendar": "effective_date_calendar",
    "output_data.metadata.critical_dates.compliance_date": "compliance_date",
    "output_data.metadata.critical_dates.compliance_date_calendar": "compliance_date_calendar",
    "output_data.metadata.critical_dates.comment_deadline": "comment_deadline",
    "output_data.metadata.critical_dates.comment_deadline_calendar": "comment_deadline_calendar",
    "output_data.metadata.critical_dates.early_adoption_date": "early_adoption_date",
    "output_data.metadata.critical_dates.early_adoption_date_calendar": "early_adoption_date_calendar",
    "output_data.metadata.critical_dates.updated_date": "updated_date",
    "output_data.metadata.critical_dates.updated_date_calendar": "updated_date_calendar",
    "output_data.metadata.critical_dates.pub_date_content": "pub_date_content",
    "output_data.metadata.critical_dates.pub_date_calendar": "pub_date_calendar",
    # --- Reconciled published date (field is `date`, NOT `value`) ---
    "output_data.reconciled_published_date.date": "reconciled_published_date",
    "output_data.reconciled_published_date.source": "reconciled_pub_source",
    "output_data.reconciled_published_date.converted": "reconciled_pub_converted",
    "output_data.reconciled_published_date.original_calendar": "reconciled_pub_original_calendar",
    "output_data.reconciled_published_date.valid": "reconciled_pub_valid",
}
