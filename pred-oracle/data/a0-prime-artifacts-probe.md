# Carver Artifacts API Probe Results

## Summary Table

| Probe | Status | Time (s) | Response Type | Length/Keys | First Item |
|-------|--------|----------|---------------|-------------|------------|
| A | 200 | 0.15 | list | len=4 | keys=21 |
| B | 404 | 0.06 | dict | keys=1 | N/A |
| C | 404 | 0.07 | dict | keys=6 | N/A |
| D | 200 | 0.08 | list | len=4 | keys=21 |
| E | 200 | 0.14 | list | len=1 | keys=21 |

## Probe Details

### Probe A

**Description:** Standard form with source_dag_id in path

**Status Code:** 200

**Time:** 0.15s

**Response Shape:** {
  "type": "list",
  "length": 4,
  "first_item_shape": {
    "top_level_keys": [
      "id",
      "artifact_id",
      "dag_id",
      "artifact_type_id",
      "source_kind",
      "source_table",
      "source_id",
      "topic_id",
      "source_metadata",
      "state",
      "input_data",
      "output_data",
      "execution_id",
      "execution_metadata",
      "error_message",
      "retry_count",
      "max_retries",
      "created_at",
      "sent_at",
      "completed_at",
      "updated_at"
    ],
    "input_data.extracted_metadata_keys": [
      "url",
      "title",
      "assets",
      "status",
      "feed_id",
      "s3_path",
      "topic_id",
      "source_id",
      "timestamp",
      "worker_id",
      "server_name",
      "source_type",
      "root_log_file",
      "extraction_method",
      "s3_content_md_path",
      "s3_content_html_path",
      "article_modified_time",
      "s3_execution_log_path",
      "s3_aggregated_content_md_path"
    ]
  }
}

### Probe B

**Description:** Bogus UUID (00000000...) in path — does path validate?

**Status Code:** 404

**Time:** 0.06s

**Response Shape:** {
  "type": "dict",
  "keys": [
    "detail"
  ]
}

### Probe C

**Description:** No path id — direct /artifacts endpoint

**Status Code:** 404

**Time:** 0.07s

**Response Shape:** {
  "type": "dict",
  "keys": [
    "error",
    "status_code",
    "message",
    "detail",
    "path",
    "hint"
  ]
}

### Probe D

**Description:** Probe A + return_type=single parameter

**Status Code:** 200

**Time:** 0.08s

**Response Shape:** {
  "type": "list",
  "length": 4,
  "first_item_shape": {
    "top_level_keys": [
      "id",
      "artifact_id",
      "dag_id",
      "artifact_type_id",
      "source_kind",
      "source_table",
      "source_id",
      "topic_id",
      "source_metadata",
      "state",
      "input_data",
      "output_data",
      "execution_id",
      "execution_metadata",
      "error_message",
      "retry_count",
      "max_retries",
      "created_at",
      "sent_at",
      "completed_at",
      "updated_at"
    ],
    "input_data.extracted_metadata_keys": [
      "url",
      "title",
      "assets",
      "status",
      "feed_id",
      "s3_path",
      "topic_id",
      "source_id",
      "timestamp",
      "worker_id",
      "server_name",
      "source_type",
      "root_log_file",
      "extraction_method",
      "s3_content_md_path",
      "s3_content_html_path",
      "article_modified_time",
      "s3_execution_log_path",
      "s3_aggregated_content_md_path"
    ]
  }
}

### Probe E

**Description:** Probe A with limit=1, offset=2 — pagination test

**Status Code:** 200

**Time:** 0.14s

**Response Shape:** {
  "type": "list",
  "length": 1,
  "first_item_shape": {
    "top_level_keys": [
      "id",
      "artifact_id",
      "dag_id",
      "artifact_type_id",
      "source_kind",
      "source_table",
      "source_id",
      "topic_id",
      "source_metadata",
      "state",
      "input_data",
      "output_data",
      "execution_id",
      "execution_metadata",
      "error_message",
      "retry_count",
      "max_retries",
      "created_at",
      "sent_at",
      "completed_at",
      "updated_at"
    ],
    "input_data.extracted_metadata_keys": [
      "url",
      "title",
      "assets",
      "status",
      "feed_id",
      "s3_path",
      "topic_id",
      "source_id",
      "timestamp",
      "worker_id",
      "server_name",
      "source_type",
      "root_log_file",
      "extraction_method",
      "s3_content_md_path",
      "s3_content_html_path",
      "article_modified_time",
      "s3_execution_log_path",
      "s3_aggregated_content_md_path"
    ]
  }
}


## Working Probe: A

**First artifact from 4 total artifacts**

### Top-Level Keys

- artifact_id
- artifact_type_id
- completed_at
- created_at
- dag_id
- error_message
- execution_id
- execution_metadata
- id
- input_data
- max_retries
- output_data
- retry_count
- sent_at
- source_id
- source_kind
- source_metadata
- source_table
- state
- topic_id
- updated_at

### input_data.extracted_metadata Keys

- article_modified_time
- assets
- extraction_method
- feed_id
- root_log_file
- s3_aggregated_content_md_path
- s3_content_html_path
- s3_content_md_path
- s3_execution_log_path
- s3_path
- server_name
- source_id
- source_type
- status
- timestamp
- title
- topic_id
- url
- worker_id

### Full JSON (First Artifact, truncated to 6000 chars)

```json
{
  "id": "4a399b31-3810-4bf4-8996-7e1a19e65e84",
  "artifact_id": "4a399b31-3810-4bf4-8996-7e1a19e65e84",
  "dag_id": "7f61eee4-1c56-44cc-b7fb-bbfcbda6a5ad",
  "artifact_type_id": "annotations-v1",
  "source_kind": "record",
  "source_table": "crawl_outcomes",
  "source_id": "864af760-bd18-4ed7-9265-14aa2b90fbef",
  "topic_id": "04878447-710c-4b80-aef1-5436b128d595",
  "source_metadata": {},
  "state": "pending",
  "input_data": {
    "id": "864af760-bd18-4ed7-9265-14aa2b90fbef",
    "source_id": "61ca1317-cd88-4234-81c9-de4a71dfb016",
    "extracted_metadata": {
      "url": "https://wmo.int/media/project-update/experts-from-five-andean-countries-participate-technical-internship-meteoswiss",
      "title": "Experts from Five Andean Countries Participate in a Technical Internship at MeteoSwiss",
      "assets": [],
      "status": "done",
      "feed_id": "8699f93b-595e-44ad-bf72-8d2e24852966",
      "s3_path": "s3://carver-prod-data/server/app.carveragents.ai/regulatory/feeds/wmo.int/327743c2_L10_news______/20260520T000430_HTML_Extraction_Strategy/c9a1f656_L5_media",
      "topic_id": "04878447-710c-4b80-aef1-5436b128d595",
      "source_id": "61ca1317-cd88-4234-81c9-de4a71dfb016",
      "timestamp": "2026-05-20T00:09:29.995087+00:00",
      "worker_id": "pid-597953",
      "server_name": "",
      "source_type": "rss",
      "root_log_file": "/tmp/carver-crawl--20260519T214656Z.log",
      "extraction_method": "firecrawl",
      "s3_content_md_path": "s3://carver-prod-data/server/app.carveragents.ai/regulatory/feeds/wmo.int/327743c2_L10_news______/20260520T000430_HTML_Extraction_Strategy/c9a1f656_L5_media/content.md",
      "s3_content_html_path": "s3://carver-prod-data/server/app.carveragents.ai/regulatory/feeds/wmo.int/327743c2_L10_news______/20260520T000430_HTML_Extraction_Strategy/c9a1f656_L5_media/content.html",
      "article_modified_time": "2026-05-19T10:54:41+02:00",
      "s3_execution_log_path": "s3://carver-prod-data/server/app.carveragents.ai/regulatory/crawl-executions//20260519T214656Z.log",
      "s3_aggregated_content_md_path": "s3://carver-prod-data/server/app.carveragents.ai/regulatory/feeds/wmo.int/327743c2_L10_news______/20260520T000430_HTML_Extraction_Strategy/c9a1f656_L5_media/aggregate_content.md"
    },
    "current_published_date": "2026-05-19T00:00:00+00:00",
    "feed_entry_id": "61ca1317-cd88-4234-81c9-de4a71dfb016"
  },
  "output_data": null,
  "execution_id": null,
  "execution_metadata": null,
  "error_message": null,
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "2026-05-20T02:00:33.283Z",
  "sent_at": null,
  "completed_at": null,
  "updated_at": "2026-05-20T02:00:33.283Z"
}
```

## Verdict


**Status: DONE**

Probe **A** succeeds with status 200, returning a list of 4 artifacts.

The working URL form is **Probe A**: the standard form with the source_dag_id in the path is correct. For external API callers, use the source_dag_id (not your own dag_id) in the path component.

**Pagination via offset works**: Probe E (offset=2, limit=1) returns a different artifact than Probe A's first item, confirming offset-based pagination is functional.

**Filters honored**: The response reflects `dag_state=completed` and `topic_id_in=04878447...` parameters.

