---
verdict: CHANGES_REQUESTED
round: 1
---
## Issues
1. The 6-bucket taxonomy does not yet satisfy the ">=2 real corpus examples per bucket" requirement. `Person` has only one example, and several `Government body` / `International body` examples are described as plausible in a global regulatory corpus rather than confirmed in this corpus, with "confirmed during --sample prompt iteration in Stage 02" deferred. Replace this with at least two explicitly real corpus examples per bucket, or clearly mark any bucket examples as verified from the current annotation snapshot. Do not defer this verification to Stage 02.
2. The response-validation design contradicts the required retry behaviour for malformed/short chunk responses. Section 4.3 defines "fewer objects than entities sent" as malformed, but then says missing/invalid individual entities default directly to `Other`; the task/rubric require malformed/short chunk responses to be detected and retried. Update the design so short/malformed chunk output is retried with a bounded policy before unresolved entities fall back to `Other`, and keep the fallback path explicit for exhausted retries.

## Notes
The rest of the spec is strong and mostly build-ready: the three-tool boundary, artifact schemas, aggregate-only behaviour, app/deck integration, and test surface are all concrete enough for Stage 02 once the two issues above are closed.
