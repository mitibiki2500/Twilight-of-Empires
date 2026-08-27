# ToE building audit

This directory contains the one-pass building-history cleanup and regression-audit utilities used for the 2026-08-27 normalization.

- `audit_buildings.py`: detects duplicate state/region/building definitions and reports government administration levels.
- `cleanup_buildings.py`: merges duplicate region/building blocks without changing population; preserves the last effective PM settings and applies the confirmed XBB administration target.
- `audit_rollbacks.py`: checks established ToE fixes for regressions.
- `building_audit_report.json`: post-cleanup structural audit.
- `rollback_audit_report.json`: established-fix regression audit.
