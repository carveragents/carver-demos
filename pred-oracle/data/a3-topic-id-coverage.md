# Topic ID Coverage Analysis

## Summary

- **Hit Rate**: 618/618 (100.0%)
- **Miss Rate**: 0/618 (0.0%)
- **Distinct Topic Names**: 5

## Top 20 Topic Names

| Rank | Topic Name | Count | Looks Like Regulator? |
|------|------------|-------|----------------------|
| 1 | Commodity Futures Trading Commission | 548 | Yes |
| 2 | Commodity Futures Trading Commission (CFTC) - USA [comments] | 66 | Yes |
| 3 | California Department of Financial Protection and Innovation | 2 | Yes |
| 4 | Alberta Securities Commission | 1 | Yes |
| 5 | Arkansas Securities Department | 1 | Yes |

## Verdict

**yes, clean join**

All event topic_ids resolve successfully to topic names. The approach of using topic_id → topic_name to populate the regulator-name field is reliable and requires no cleanup.
