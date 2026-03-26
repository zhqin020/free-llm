# Implementation Plan - SQLite Persistence for Providers & Models

Transition from [config.yaml](file:///home/watson/work/freellm/config.yaml) to a SQLite database for managing providers, models, and API keys. This will allow for easier updates via the UI and persistent storage of health metrics.

## Proposed Changes

### Database Layer

#### [NEW] [database.py](file:///home/watson/work/freellm/src/database.py)
- Implement `DatabaseManager` using `sqlite3`.
- Schema:
  - [providers](file:///home/watson/work/freellm/src/provider.py#73-75): `name` (PK), `type`, `api_key`, `url`, [free](file:///home/watson/work/freellm/src/admin.py#9-70), `status`, `token_price_1k` (for sorting), `max_quota_min`, `max_quota_day`, `current_quota_min`, `current_quota_day`, `last_reset_min`, `last_reset_day`, `retry_count`, `avg_error_rate`, [p99_latency](file:///home/watson/work/freellm/src/provider.py#57-61).
  - [models](file:///home/watson/work/freellm/src/main.py#78-93): [id](file:///home/watson/work/freellm/src/provider.py#67-69) (PK), `provider_name` (FK), `model_id`, `tags` (JSON), [free](file:///home/watson/work/freellm/src/admin.py#9-70), `price_input_1k`, `price_output_1k`, `last_used_at`, `success_count`, `error_count`.

### Persistence & Quota Logic

#### [MODIFY] [provider.py](file:///home/watson/work/freellm/src/provider.py)
- Add `check_and_update_quota()` method to [ProviderState](file:///home/watson/work/freellm/src/provider.py#41-61).
- Add `pricing` fields to [ProviderState](file:///home/watson/work/freellm/src/provider.py#41-61) and [ModelState](file:///home/watson/work/freellm/src/provider.py#7-39).

#### [MODIFY] [scheduler.py](file:///home/watson/work/freellm/src/scheduler.py)
- Update [_score()](file:///home/watson/work/freellm/src/scheduler.py#31-61) to:
  - Return `-float('inf')` if quota is exhausted.
  - Incorporate `token_price_1k` into scoring (cheaper models rank higher).
- Group candidates by [free](file:///home/watson/work/freellm/src/admin.py#9-70) status and sort by `token_price_1k` before returning.

#### [MODIFY] [main.py](file:///home/watson/work/freellm/src/main.py)
- Replace [load_config](file:///home/watson/work/freellm/src/config.py#47-66) logic with `DatabaseManager.load_all()`.
- Ensure health and quota updates are persisted.
- Add `POST /admin/providers/update` for key, URL, price, and quota edits.

#### [MODIFY] [static/index.html](file:///home/watson/work/freellm/src/static/index.html)
- Display quota usage progress bars.
- Group providers into "Free" and "Paid" sections.
- Add "Edit" modal for all fields including pricing and quotas.

## Verification Plan

### Automated Tests
- `tests/test_database.py`: CRUD and quota reset logic.
- `tests/test_scheduler_pricing.py`: Verify selection based on price and quota.

### Manual Verification
1. Verify "Free" models are prioritized.
2. Verify "Paid" models are sorted by price.
3. Verify request is blocked when `current_quota_min` or `current_quota_day` is hit.

### Manual Verification
1. Run migration script and verify DB is populated from [config.yaml](file:///home/watson/work/freellm/config.yaml).
2. Sync from GitHub and verify new models appear in DB without overwriting keys.
3. Update an API key via UI/Curl and verify it persists across restarts.
