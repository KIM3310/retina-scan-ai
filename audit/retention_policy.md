# Audit Log Retention Policy

## Retention window

**7 years from event timestamp**, aligned with HIPAA §164.530(j)(2) which requires 6-year retention of audit documentation, plus a 1-year safety margin that absorbs typical legal-hold escalation latency.

State-specific overrides:
- California CMIA: 7 years from last treatment date (already covered).
- New York: 6 years from creation (covered).
- Texas Medical Records Privacy Act: 7 years (covered).
- International operators: operator's compliance officer determines equivalent retention.

## Storage strategy

### Hot tier (0-90 days)

- Storage: primary database (e.g., PostgreSQL with partitioning on `event_timestamp`).
- Access: sub-second query latency for compliance-officer ad-hoc queries.
- Cost: full hot-tier cost.

### Warm tier (90 days – 2 years)

- Storage: columnar store (e.g., Snowflake, BigQuery) or partitioned Parquet on S3/GCS.
- Access: seconds-to-minutes query latency; acceptable for quarterly audits.
- Cost: ~10-20% of hot tier.

### Cold tier (2-7 years)

- Storage: S3 Glacier Deep Archive or equivalent cloud cold storage with Object Lock.
- Access: hours-to-days retrieval latency; only pulled for legal hold or regulatory inquiry.
- Cost: ~1-2% of hot tier.

### Purge (>7 years)

Events older than 7 years are automatically deleted after:

1. A scheduled purge identifies candidate events.
2. The compliance officer reviews the purge manifest (number of events, date range).
3. The compliance officer approves via a signed form (captured as a `system.retention_purge_approved` event in the audit log itself).
4. The purge runs; a final `system.retention_purge_executed` event is logged.

The approval event and purge-executed event are themselves subject to the retention policy — but the chain of evidence for a given purge is retained indefinitely in a separate compliance-decisions store.

## Partition strategy

Audit events partition by `event_timestamp` in monthly buckets. Partition boundaries:

```
2026-04/  (current month, hot)
2026-03/  (hot)
...
2026-01/  (hot → warm boundary at 90 days)
...
2024-04/  (warm → cold boundary at 2 years)
...
2019-04/  (cold → purge candidate at 7 years, requires compliance review)
```

## Legal hold

If a legal hold notice is received for any patient, study, or user:

1. All events referencing the subject are flagged with `legal_hold=true`.
2. The retention-purge process excludes flagged events.
3. The flag is removed only by explicit compliance-officer action, recorded as a `system.legal_hold_released` event.

Legal hold override does NOT extend retention for events not subject to the hold. It is additive, not blanket.

## Chain-of-custody verification

Quarterly process:

1. Run `audit/search_tools.py verify-chain --from-date <last-verification>`.
2. Confirm no hash-chain breaks detected.
3. Emit a `system.chain_verification_completed` event documenting the result.
4. If a break is detected, trigger incident response (see `docs/clinical/incident-response.md`).

## Roles with access to audit data

| Role | Hot tier | Warm tier | Cold tier | Purge |
|------|----------|-----------|-----------|-------|
| Clinician | No | No | No | No |
| Admin (system) | No | No | No | No |
| Compliance officer (read) | Yes | Yes | Yes | No |
| Compliance officer (purge approver) | Yes | Yes | Yes | Approve only |
| Engineering (break-glass, time-boxed) | Read with secondary approval | No | No | No |
| External auditor (time-boxed) | Read via exported subset | Read via exported subset | No | No |

No role has mutate or delete access to committed events. Destruction is only via the documented purge process, not ad-hoc DELETE statements.

## Storage size projections

Reference estimate for a 100-clinician / 1000-study-per-day deployment:

- Events per day: roughly 20,000 (multiple events per study — receive, read, classify, review, close).
- Event size: ~1.5 KB average JSON.
- Daily volume: ~30 MB raw.
- Yearly volume: ~11 GB raw.
- 7-year volume: ~77 GB raw. With compression: ~15-25 GB.

These volumes are trivial at cold-storage prices (well under $1/month for a 100-clinician deployment's cold tier).

## References

- HIPAA Security Rule §164.312(b): audit controls requirement.
- HIPAA §164.530(j)(2): 6-year retention of audit documentation.
- State law summary: https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/combined-regulation-text/index.html
- NIST SP 800-92: Guide to Computer Security Log Management
