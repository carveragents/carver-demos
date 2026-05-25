# A0 — Annotations Endpoint Pagination Probe

**Timestamp:** 2025-05-19  
**Endpoint:** `GET /api/v1/core/annotations`  
**Test Topic ID:** `4d27ba32-9110-4ced-841d-ec168a99f886`

---

## Probe Summary

| Probe | HTTP Status | Response Type | Item Count | Pagination Headers | First Entry ID |
|-------|-------------|---------------|------------|-------------------|---|
| A (baseline, no pagination) | 200 | list | 670 | None | `9dedd0d3-3419-4f9d-b1df-725dbc56bf1e` |
| B (limit=10, offset=0) | 200 | list | 670 | None | `9dedd0d3-3419-4f9d-b1df-725dbc56bf1e` |
| C (limit=10, offset=10) | 200 | list | 670 | None | `9dedd0d3-3419-4f9d-b1df-725dbc56bf1e` |
| D (limit=10000, offset=0) | 200 | list | 670 | None | `9dedd0d3-3419-4f9d-b1df-725dbc56bf1e` |

---

## Key Findings

### Pagination Behavior
- **A vs B:** Both return 670 items. Probe B specifies `limit=10`, but response is unchanged.
- **B vs C:** Both return 670 items and the same first entry ID. Probe C offsets to row 10, but response is unchanged.
- **D (large limit):** Returns 670 items; below the 10,000 limit requested.
- **Response headers:** No `X-Total-Count`, `Link`, `Content-Range`, `X-Limit`, or `X-Offset` headers present in any response.

### Pagination Status
**The `/api/v1/core/annotations` endpoint IGNORES limit/offset parameters.** The server returns the full result set (670 annotations for this topic) regardless of pagination parameters passed.

---

## Sample Responses

### Probe A: Baseline (no pagination)
First 2 items:
```json
[
  {
    "annotation": {
      "scores": {
        "impact": {"label": "high", "score": 9, "confidence": 0.95},
        "urgency": {"basis": "past_deadline", "label": "medium", "score": 5, "confidence": 0.9},
        "relevance": {"label": "high", "score": 9.0, "confidence": 0.925}
      },
      "entry_id": "c83abf6a-ebc7-4c97-addc-40e8324ef8c8",
      ...
    }
  },
  {
    "annotation": {
      "scores": {
        "impact": {"label": "high", "score": 8, "confidence": 0.9},
        "urgency": {"basis": "future_deadline", "label": "high", "score": 9, "confidence": 0.95},
        "relevance": {"label": "high", "score": 8.5, "confidence": 0.925}
      },
      "entry_id": "825099d4-b189-4e0a-a9c2-6d921d597486",
      ...
    }
  }
]
```

### Probe B: Small limit (limit=10, offset=0)
First 2 items (identical to Probe A):
```json
[
  {
    "annotation": {
      "scores": {
        "impact": {"label": "high", "score": 9, "confidence": 0.95},
        "urgency": {"basis": "past_deadline", "label": "medium", "score": 5, "confidence": 0.9},
        "relevance": {"label": "high", "score": 9.0, "confidence": 0.925}
      },
      "entry_id": "c83abf6a-ebc7-4c97-addc-40e8324ef8c8",
      ...
    }
  },
  {
    "annotation": {
      "scores": {
        "impact": {"label": "high", "score": 8, "confidence": 0.9},
        "urgency": {"basis": "future_deadline", "label": "high", "score": 9, "confidence": 0.95},
        "relevance": {"label": "high", "score": 8.5, "confidence": 0.925}
      },
      "entry_id": "825099d4-b189-4e0a-a9c2-6d921d597486",
      ...
    }
  }
]
```

### Probe C: Offset (limit=10, offset=10)
First 2 items (identical to Probe A—offset is ignored):
```json
[
  {
    "annotation": {
      "scores": {
        "impact": {"label": "high", "score": 9, "confidence": 0.95},
        "urgency": {"basis": "past_deadline", "label": "medium", "score": 5, "confidence": 0.9},
        "relevance": {"label": "high", "score": 9.0, "confidence": 0.925}
      },
      "entry_id": "c83abf6a-ebc7-4c97-addc-40e8324ef8c8",
      ...
    }
  },
  {
    "annotation": {
      "scores": {
        "impact": {"label": "high", "score": 8, "confidence": 0.9},
        "urgency": {"basis": "future_deadline", "label": "high", "score": 9, "confidence": 0.95},
        "relevance": {"label": "high", "score": 8.5, "confidence": 0.925}
      },
      "entry_id": "825099d4-b189-4e0a-a9c2-6d921d597486",
      ...
    }
  }
]
```

### Probe D: Large limit (limit=10000, offset=0)
First 2 items (identical to Probe A):
```json
[
  {
    "annotation": {
      "scores": {
        "impact": {"label": "high", "score": 9, "confidence": 0.95},
        "urgency": {"basis": "past_deadline", "label": "medium", "score": 5, "confidence": 0.9},
        "relevance": {"label": "high", "score": 9.0, "confidence": 0.925}
      },
      "entry_id": "c83abf6a-ebc7-4c97-addc-40e8324ef8c8",
      ...
    }
  },
  {
    "annotation": {
      "scores": {
        "impact": {"label": "high", "score": 8, "confidence": 0.9},
        "urgency": {"basis": "future_deadline", "label": "high", "score": 9, "confidence": 0.95},
        "relevance": {"label": "high", "score": 8.5, "confidence": 0.925}
      },
      "entry_id": "825099d4-b189-4e0a-a9c2-6d921d597486",
      ...
    }
  }
]
```

---

## Verdict

**The `/api/v1/core/annotations` endpoint does NOT support server-side pagination via `limit` and `offset` query parameters.** The server silently ignores these parameters and returns the full result set. This has two implications for annotation pulling:

1. **No chunking possible:** To pull all annotations for a set of topics, we cannot paginate through results. The endpoint will always return everything matched by the filter, regardless of parameters.
2. **Response size risk:** For topics with high annotation density (this test had 670 for a single topic), expect large single responses. For multiple topics or wide filters, response payloads could become substantial.

**Recommendation:** If chunking is required, request pagination support from the Carver Feeds API team, or consider fetching by narrow topic slices and accepting larger per-request payloads.
