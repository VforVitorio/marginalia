# Research & audit reports

Deep, code-verified audits of marginalia used to plan the post-audit remediation
work. Each report is the near-verbatim output of a dedicated audit pass, kept as a
durable record of *why* each improvement item exists. The actionable items are
tracked as GitHub issues under the post-audit epic.

| Report | Scope |
|---|---|
| [AUDIT_BACKEND.md](AUDIT_BACKEND.md) | `backend/marginalia/**` — OCR + model loading, ingest/structure/export pipeline, API/jobs/SSE. Items `BE-01`…`BE-25`. |
| [AUDIT_FRONTEND_ARCHITECTURE.md](AUDIT_FRONTEND_ARCHITECTURE.md) | `frontend/src/**` + overall architecture + future-feature feasibility. Items `FE-01`…`FE-23`, `AR-01`…`AR-05`. |

Each item carries a stable ID (`BE-nn` / `FE-nn` / `AR-nn`), a priority (P0–P3),
an effort estimate (S/M/L), and a `file:line` anchor. The IDs are referenced from
the tracking issues so a PR can be traced back to the finding that motivated it.
