## 1. Project Implementation Summary

**Project name**  
Grist Finance API Connector

**Short purpose statement**  
A self-hosted connector service that pulls financial data from external APIs and imports it into a self-hosted Grist instance safely, repeatedly, and without duplicate creation.

**Intended deployment context**  
Self-hosted Docker-based environment with Grist already running in a container, the connector running as a separate service on the same network, optional scheduler support, and local persistent storage for logs and sync state.

**Implementation goal**  
Prepare a maintainable, extensible connector service that can authenticate to at least one external provider, transform provider data into Grist-compatible records, import them through the Grist REST API, support scheduled and manual sync, preserve sync state, and expose operational status.

**What will actually be built**  
The implementation should produce a standalone containerised connector application with clear separation between provider adapters, transformation logic, Grist API integration, scheduling, logging, and state persistence. It should support source authentication, paginated and windowed/cursor-based retrieval, stable deduplication, batched writes to Grist, dry-run mode, health checks, structured logging, startup validation, and persistent sync metadata. It should also include deployment artifacts, test coverage with mocks and integration paths, and documentation for setup, operation, and recovery.

## 2. Implementation Scope Restatement

### In Scope
- Self-hosted connector service running separately from Grist
- Pulling data from one or more external APIs
- Authenticating to source APIs
- Transforming source data into Grist-compatible row structures
- Writing records to Grist through the Grist REST API only
- Duplicate prevention using stable external identifiers
- Scheduled sync execution
- Manual sync execution
- Import logging and status reporting
- Staging/raw import table support in Grist
- Configurable import behaviour
- Container-based deployment
- Safe handling of secrets and credentials
- Retry and failure handling for common operational issues
- Persistent sync state such as last sync time, cursors, and job history
- Health status endpoint or equivalent operational check
- Dry-run mode
- Configurable log verbosity
- Extensible architecture for multiple providers

### Out of Scope
- Direct writes to Grist backend databases
- Full accounting logic inside the connector
- Rich budgeting, reporting, or categorisation logic inside the connector
- Native banking integrations embedded inside Grist
- Real-time event streaming unless added later
- Mobile or desktop apps
- Multi-tenant SaaS-style user management
- Complex workflow orchestration platforms
- Replacing Grist as the primary UI or analysis layer
- Direct Home Assistant integration
- OTA-style embedded update logic
- Two-way sync unless added in a later phase

## 3. System Breakdown

### Component: Configuration Loader
- **Purpose:** Load, validate, and expose runtime configuration.
- **Responsibilities:** Read environment variables and optional config files, validate required values, apply defaults, separate secrets from non-secret settings.
- **Key inputs:** Environment variables, optional config template, runtime flags.
- **Key outputs:** Validated application configuration object.
- **Dependencies:** Environment, schema validation library.
- **Implementation notes:** Fail fast on missing required secrets or invalid table/document settings.

### Component: Provider Adapter Interface
- **Purpose:** Standardise how external providers are integrated.
- **Responsibilities:** Authentication, fetch accounts/balances/transactions, pagination, cursor/window support, provider-specific normalisation.
- **Key inputs:** Provider config, credentials, sync state, date window/cursor.
- **Key outputs:** Normalised import records plus updated provider sync cursor/state candidates.
- **Dependencies:** HTTP client, provider-specific API contracts.
- **Implementation notes:** Keep provider-specific logic isolated from orchestration.

### Component: Transformation Layer
- **Purpose:** Convert provider payloads into internal import models and Grist row payloads.
- **Responsibilities:** Field mapping, normalisation, validation, metadata tagging, staging-row preparation.
- **Key inputs:** Provider responses, mapping configuration.
- **Key outputs:** Validated internal records and target row objects.
- **Dependencies:** Domain models, mapping rules.
- **Implementation notes:** Preserve original external IDs and source metadata at all times.

### Component: Deduplication and Matching Service
- **Purpose:** Prevent duplicate imports and handle matching strategy.
- **Responsibilities:** Compare incoming records with Grist records, apply duplicate policy, determine insert/update/skip/conflict outcomes.
- **Key inputs:** Incoming normalised records, existing Grist rows, duplicate strategy config.
- **Key outputs:** Write plan and import outcome counts.
- **Dependencies:** Grist API client, identifier rules.
- **Implementation notes:** Stable external ID is the primary dedupe key; fallback logic should not be invented without approval.

### Component: Grist API Client
- **Purpose:** Encapsulate all interaction with Grist.
- **Responsibilities:** Authenticate to Grist API, read target table rows needed for matching, batch-create/update rows, handle partial failures.
- **Key inputs:** Grist base URL, API key, document ID, table names, row payloads.
- **Key outputs:** Read results, write results, error details.
- **Dependencies:** HTTP client, config loader.
- **Implementation notes:** Must be the only path used for writes; no direct DB access.

### Component: Sync Orchestrator
- **Purpose:** Execute a complete sync job end to end.
- **Responsibilities:** Trigger provider fetch, transform, dedupe, write, persist state, record summary, enforce dry-run behavior.
- **Key inputs:** Source config, runtime config, current sync state.
- **Key outputs:** Sync job result, updated sync state, logs, metrics/status summary.
- **Dependencies:** Provider adapter, transformer, dedupe service, Grist client, state store, logger.
- **Implementation notes:** Only commit last successful sync state after successful completion of the required write phase.

### Component: Scheduler
- **Purpose:** Trigger sync runs on schedule.
- **Responsibilities:** Support internal scheduling or external-trigger compatibility, handle per-source schedules.
- **Key inputs:** Schedule configuration, source enablement flags.
- **Key outputs:** Job triggers.
- **Dependencies:** Sync orchestrator.
- **Implementation notes:** Manual sync must still work independently of scheduler choice.

### Component: State Store
- **Purpose:** Persist sync progress and job metadata across restarts.
- **Responsibilities:** Store last successful sync time, cursors/tokens, job history, optional checkpoints.
- **Key inputs:** Sync outcomes, provider cursors, timestamps.
- **Key outputs:** Persisted state records.
- **Dependencies:** Local filesystem, SQLite, or Grist tables where chosen.
- **Implementation notes:** Specification leaves storage choice open; initial default should be explicit and documented.

### Component: Logging and Monitoring
- **Purpose:** Support operations and diagnostics.
- **Responsibilities:** Structured or human-readable logs, import summaries, failure details, health reporting.
- **Key inputs:** Application events, job outcomes, exception details.
- **Key outputs:** Logs, health endpoint/status output.
- **Dependencies:** Logger, optional HTTP server.
- **Implementation notes:** Never log secret material.

### Component: Health/Operational Endpoint
- **Purpose:** Provide a simple readiness/liveness operational check.
- **Responsibilities:** Expose health status and possibly last sync summary.
- **Key inputs:** Application state, dependency health checks.
- **Key outputs:** Health response.
- **Dependencies:** Runtime app shell, config, state store.
- **Implementation notes:** Keep scope operational, not a full admin UI.

## 4. Proposed Architecture for Build

### Runtime components
- Connector application service
- Internal or external scheduler
- Self-hosted Grist service
- Persistent state storage layer
- Local log output or structured log sink

### Service boundaries
- Connector owns source API communication, transformation, dedupe, sync orchestration, and health checks.
- Grist owns record storage, user-facing tables, formulas, reporting, and manual correction.
- Scheduler only triggers jobs; it should not contain business logic.

### Storage boundaries
- Grist stores imported business records and optional import log/raw tables.
- Connector state store holds sync cursors, last successful sync markers, and job metadata.
- Local persistent storage is required if using files or SQLite for state.

### API boundaries
- External provider APIs are read-only sources from the connector’s perspective.
- Grist REST API is the only allowed write/read integration into Grist.
- Optional connector endpoint may expose health and manual trigger/status operations.

### Data flow
1. Scheduler or operator triggers sync.
2. Connector loads validated config and current persisted state.
3. Provider adapter authenticates and fetches data using window or cursor.
4. Transformation layer normalises records into internal import objects.
5. Dedupe service reads relevant Grist rows and plans insert/update/skip/conflict actions.
6. Grist API client performs batched writes unless dry-run mode is enabled.
7. Sync summary and outcome are logged and persisted.
8. Last successful sync state is updated only after successful completion.

### Integration points
- Provider HTTP APIs
- Grist HTTP API
- Local filesystem or SQLite for sync state
- Optional manual trigger endpoint
- Docker networking between connector and Grist

### Failure boundaries
- Provider auth failures stop only the affected source sync.
- Provider outages and rate limits trigger retry/backoff within limits.
- Grist unavailability aborts the write phase and prevents false success marking.
- Partial batch failures must be logged and handled according to configured mode.
- Schema mismatch in Grist is a hard import failure.

### Operational boundaries
- Startup validation must confirm required config before running.
- Health check should expose service readiness.
- Logging must make job status diagnosable without reading code.
- Deployment should remain self-hosted and cloud-independent.

### Simple text diagram
```text
[Scheduler/Manual Trigger]
            |
            v
   [Connector Service]
   |   Config Loader
   |   Sync Orchestrator
   |   Provider Adapter(s)
   |   Transform + Validate
   |   Dedupe/Match
   |   Grist API Client
   |   State Store
   |   Logging/Health
   |
   +----read----> [External API Provider(s)]
   |
   +----read/write via REST----> [Grist]
   |
   +----persist----> [Local State Store / SQLite / Chosen Store]
```

## 5. Data and Interface Preparation

### Key entities
- **SourceConfig**
  - Provider name
  - Base URL
  - auth method
  - enabled flag
  - schedule
  - duplicate policy
  - date window/lookback
- **SyncState**
  - source identifier
  - last successful sync timestamp
  - cursor/token
  - last job status
  - last job summary
- **NormalizedTransaction**
  - external_id
  - source_name
  - account_id
  - transaction_date
  - description
  - amount
  - currency
  - external_reference
  - raw payload reference or hash if needed
- **NormalizedAccount**
  - external_account_id
  - source_name
  - account_name/type if provided
  - currency
  - status fields if supported
- **ImportJobLog**
  - source
  - start time
  - end time
  - duration
  - fetched count
  - inserted count
  - updated count
  - skipped count
  - failed count
  - status
  - error details

### Table/model suggestions
Recommended Grist logical tables from the specification:
- `Accounts`
- `Raw_Import_Transactions`
- `Transactions`
- `Import_Log`
- `Import_Sources`
- `Category_Map` optional

Suggested internal code models:
- `ProviderRecord`
- `NormalizedRecord`
- `WritePlan`
- `SyncJobResult`
- `PersistedSyncState`

### API client boundaries
- **Provider client boundary**
  - Authenticate
  - Fetch paged data
  - Convert provider pagination/cursor model into internal iterables
- **Grist client boundary**
  - Read rows from configured document/table
  - Batch insert rows
  - Batch update rows
  - Report row-level and batch-level failures

### Input/output contracts
- **Provider adapter output**
  - List/stream of normalised records
  - Next cursor candidate
  - Fetch summary
- **Transformation output**
  - Validated internal record
  - Rejected record with reason
- **Dedupe output**
  - `insert`, `update`, `skip`, or `conflict`
- **Sync result output**
  - Job metadata
  - counts by action
  - success/failure state
  - persisted next state only if successful

### Event or job flow
- Startup validation
- Trigger received
- Load source config
- Load sync state
- Fetch source records
- Transform and validate
- Read existing Grist matches
- Build write batches
- Execute or simulate writes
- Record logs and persist outcome
- Update last successful state if appropriate

### Validation rules
- Required config must exist at startup
- Required secrets must exist before sync begins
- Normalised records must contain stable external ID where available
- Dates, amount, currency, source/provider name, and account identifier should be normalised where present
- Invalid/malformed records should be rejected and logged without crashing whole sync where safe
- Table/document existence errors must fail safely

### Identifiers and deduplication keys
- Primary dedupe key: stable source transaction/record ID
- Required metadata tag: source/provider name
- Match lookup should include source context to avoid collisions across providers
- Assumption: dedupe key is effectively `(source_name, external_id)` unless the selected provider guarantees global uniqueness

### Mapping/transformation stages
1. Raw provider payload
2. Provider-specific normalisation
3. Internal canonical record
4. Validation and enrichment with source metadata
5. Duplicate/match resolution
6. Grist row payload generation
7. Optional staging table write first

## 6. Configuration Preparation

### User-configurable settings

| Setting name | Purpose | Format/type | Example | Required |
|---|---|---|---|---|
| `SOURCE_ENABLED` | Enable/disable source sync | boolean | `true` | Required per source |
| `SYNC_SCHEDULE` | Schedule for automatic sync | cron/string | `0 * * * *` | Optional if manual only |
| `GRIST_DOC_ID` | Target Grist document | string | `abc123xyz` | Required |
| `GRIST_TRANSACTIONS_TABLE` | Target transaction table | string | `Raw_Import_Transactions` | Required |
| `GRIST_ACCOUNTS_TABLE` | Target account table | string | `Accounts` | Optional if accounts supported |
| `IMPORT_LOOKBACK_DAYS` | Date-window sync lookback | integer | `30` | Optional |
| `DUPLICATE_MODE` | Matching strategy | enum | `skip_existing` | Required |
| `DRY_RUN` | Simulate without writes | boolean | `false` | Optional |
| `BATCH_SIZE` | Write batch size | integer | `100` | Optional |
| `LOG_LEVEL` | Log verbosity | enum | `info` | Optional |

### Install-time settings

| Setting name | Purpose | Format/type | Example | Required |
|---|---|---|---|---|
| `CONNECTOR_IMAGE` | Container image reference | string | `grist-finance-connector:latest` | Required |
| `CONTAINER_NAME` | Service name | string | `grist-finance-connector` | Optional |
| `DOCKER_NETWORK` | Network attachment | string | `grist_net` | Required |
| `STATE_STORAGE_PATH` | Persistent state path | path | `/data/state` | Required if file/SQLite state used |
| `SERVICE_PORT` | Connector port for health/manual endpoints | integer | `8080` | Optional |
| `SCHEDULER_MODE` | Internal vs external scheduling | enum | `internal` | Required |
| `GRIST_BASE_URL` | Internal Grist hostname/url | URL | `http://grist:8484` | Required |

### Secret values

| Setting name | Purpose | Format/type | Example | Required |
|---|---|---|---|---|
| `SOURCE_API_KEY` | Provider authentication | secret string | `***` | Required if API-key auth used |
| `SOURCE_BEARER_TOKEN` | Provider bearer token | secret string | `***` | Optional depending on provider |
| `SOURCE_OAUTH_CLIENT_SECRET` | OAuth secret | secret string | `***` | Optional depending on provider |
| `SOURCE_REFRESH_TOKEN` | OAuth refresh token | secret string | `***` | Optional depending on provider |
| `GRIST_API_KEY` | Grist API auth | secret string | `***` | Required |
| `WEBHOOK_SECRET` | Future/manual trigger protection if implemented | secret string | `***` | Optional |
| `STATE_DB_CREDENTIALS` | External state store auth if used | secret object/string | `***` | Optional |

### Optional advanced settings

| Setting name | Purpose | Format/type | Example | Required |
|---|---|---|---|---|
| `RETRY_COUNT` | Retry limit | integer | `3` | Optional |
| `RETRY_BACKOFF_MS` | Backoff base | integer | `1000` | Optional |
| `API_TIMEOUT_MS` | HTTP timeout | integer | `15000` | Optional |
| `CURSOR_MODE` | Source-specific cursor handling | enum | `provider_default` | Optional |
| `FIELD_MAPPING_OVERRIDES` | Custom field mappings | JSON/object | `{...}` | Optional |
| `CONFLICT_MODE` | Conflict handling mode | enum | `log_and_continue` | Optional |
| `IMPORT_FILTERS` | Custom filters | JSON/object | `{ "accounts": ["main"] }` | Optional |
| `JSON_LOGGING` | Structured logs | boolean | `true` | Optional |
| `HTTP_PROXY` | Proxy settings | URL | `http://proxy:3128` | Optional |
| `TLS_VERIFY` | TLS verification behavior | boolean | `true` | Optional |

## 7. Deployment Preparation

### Expected runtime environment
- Self-hosted machine or server with Docker or equivalent container runtime
- Existing self-hosted Grist instance reachable on the container network
- Persistent storage available for connector state/log needs
- Optional reverse proxy if browser access to connector endpoints is desired

### Container/services required
- Grist container
- Connector container
- Optional scheduler container or host cron if scheduler is external
- Optional reverse proxy
- Optional SQLite file storage inside mounted volume if chosen for state

### Network assumptions
- Connector can reach Grist over internal hostname
- Connector can reach external provider APIs outbound
- DNS resolution for provider APIs is available
- If using reverse proxy, internal routing to connector health/status endpoint is configured

### Storage/persistence needs
- Persist last successful sync state across restarts
- Persist cursors/tokens/checkpoints if required by provider
- Retain job history and possibly local logs
- Persistent volume required if state is file- or SQLite-based

### Startup order considerations
- Grist should be reachable before first successful sync
- Connector may start before Grist if it handles retry/health gracefully, but startup validation should clearly indicate readiness state
- Scheduler should not trigger writes until connector config is valid

### Health check expectations
- Liveness: service process is running
- Readiness: config valid, state store accessible, optional Grist reachability check
- Health response should be suitable for Docker/container orchestration checks

### Environment variable handling
- Secrets via environment variables or secret store
- Non-secret defaults documented in `.env.example`
- Startup validation should identify missing required values clearly
- Logs must mask or exclude secret values

### Deployment artifacts that should exist
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `README.md`
- Config template or settings reference
- Optional bootstrap script for local state path creation
- Optional sample Grist schema guidance
- Upgrade/restart notes for preserving sync state

## 8. Testing Preparation

### Test strategy
Use layered testing with mocked provider and mocked Grist for fast validation, then integration tests for real container-to-container communication and real Grist API writes. Prioritise idempotency, failure safety, state persistence, and configuration validation.

### Test layers
- Unit tests
- Component/service tests
- API contract tests for provider adapters and Grist client
- Integration tests
- Container/deployment smoke tests
- Recovery/restart tests

### Required test types
- Startup/config validation tests
- Provider auth tests
- Pagination tests
- Window/cursor sync tests
- Transformation/mapping tests
- Deduplication tests
- Batch write tests
- Dry-run tests
- Logging summary tests
- Health endpoint tests
- Retry/backoff tests
- State persistence tests
- Multi-source metadata tagging tests

### Key success paths
- Clean startup with valid config
- Manual sync imports expected transactions
- Repeated sync does not create duplicates
- Scheduled sync runs automatically
- Pagination retrieves all expected records
- Batch writes succeed across multiple batches
- Dry-run produces preview/log without writes
- Logs include expected summary fields
- Restart resumes from persisted state
- Multi-source imports are correctly tagged

### Negative/fault paths
- Invalid source credentials
- Missing secret at startup
- Source rate limiting
- Source timeout/DNS/unavailability
- Grist unavailable during write
- Missing or renamed Grist table
- Schema mismatch in Grist
- Corrupt source payload
- Duplicate external ID collision
- Partial batch write failure

### Recovery/restart paths
- Connector restart after successful sync
- Interrupt during large sync and safe rerun
- Recovery after source outage
- Recovery after Grist outage
- Scheduled sync resuming without duplicate creation

### Acceptance validation approach
Validate directly against the specification’s acceptance criteria:
- Deploy in self-hosted container environment
- Authenticate to at least one source API
- Connect to Grist
- Import transactions correctly
- Prevent duplicates on rerun
- Avoid corrupting existing data on failed sync
- Expose clear logs
- Externalise config and secrets
- Execute scheduled sync successfully
- Support usable dry-run mode
- Preserve sync state across restarts
- Make common failures diagnosable

### What should be mocked
- External provider API responses
- Rate-limit and auth failures
- Malformed payloads
- Grist API success/failure responses for fast component tests

### What should be integration-tested for real
- Connector to real Grist container communication
- Real HTTP auth flow for configured provider where feasible
- Container startup behavior
- Persistence across container restarts

### What should be tested first
- Config validation
- Grist API client
- Provider adapter contract
- Dedupe/idempotency logic
- Dry-run behavior

## 9. Work Breakdown and Build Order

### Phase 1: Project scaffolding
- Set up repository structure
- Choose implementation stack
- Add base app entrypoint, test harness, linting, and package management
- Define configuration schema and domain model placeholders
- Milestone: runnable project skeleton with documented setup

### Phase 2: Configuration loader and startup validation
- Implement config parsing and validation
- Define required vs optional settings
- Add secret handling rules
- Add startup validation errors
- Depends on: Phase 1
- Complete before next phase: validated config available to all modules
- Milestone: service can start and fail clearly on bad config

### Phase 3: Core domain models and contracts
- Define internal models for source records, normalised records, sync state, and job results
- Define provider adapter interface and Grist client interface
- Define duplicate strategy enums and write plan model
- Depends on: Phase 2
- Complete before next phase: stable internal contracts agreed
- Milestone: shared models/interfaces frozen enough for implementation

### Phase 4: Grist API client
- Implement authenticated Grist REST access
- Add table/document validation helpers
- Add row read and batched write support
- Add failure handling and response parsing
- Depends on: Phase 3
- Complete before next phase: target integration usable in isolation
- Milestone: records can be read/written to a test Grist document

### Phase 5: State persistence
- Choose initial state store approach
- Implement sync state read/write and job history persistence
- Ensure persistence across restarts
- Depends on: Phase 3
- Complete before next phase: state can survive crashes/restarts
- Milestone: state store tested and stable

### Phase 6: Provider adapter framework
- Build provider adapter base contract
- Implement one example provider
- Add auth, pagination, window/cursor handling
- Depends on: Phase 3
- Complete before next phase: at least one provider returns normalised records
- Milestone: source fetch works in tests

### Phase 7: Transformation and validation layer
- Implement provider-to-canonical field mapping
- Add validation/rejection paths
- Preserve external IDs and metadata tagging
- Depends on: Phase 6
- Complete before next phase: clean internal records ready for dedupe/write
- Milestone: transformation outputs stable canonical records

### Phase 8: Deduplication and upsert planning
- Implement matching against Grist records
- Support configured duplicate modes
- Generate insert/update/skip/conflict plan
- Depends on: Phase 4 and Phase 7
- Complete before next phase: idempotent write plan proven by tests
- Milestone: repeated sync windows are safe

### Phase 9: Sync orchestrator
- Wire fetch, transform, dedupe, write, state update, and logging
- Implement dry-run mode
- Enforce success/failure state rules
- Depends on: Phases 4, 5, 7, 8
- Complete before next phase: manual sync works end to end
- Milestone: end-to-end manual sync to Grist

### Phase 10: Scheduling and health checks
- Add internal scheduler or external trigger compatibility
- Support per-source schedules
- Add health/readiness endpoint
- Depends on: Phase 9
- Complete before next phase: unattended operation available
- Milestone: scheduled syncs observable and controlled

### Phase 11: Observability and operational reporting
- Add structured/human-readable logs
- Add import summaries and error diagnostics
- Add recent sync status output if exposed
- Depends on: Phase 9
- Complete before next phase: operators can diagnose common failures
- Milestone: logs and health output satisfy operational requirements

### Phase 12: Test completion
- Implement full unit/component/integration coverage
- Add fault and restart scenarios
- Validate acceptance criteria
- Depends on: all prior phases
- Complete before next phase: minimum confidence for deployment
- Milestone: test suite covers success, fault, and recovery flows

### Phase 13: Deployment packaging and documentation
- Create Dockerfile, compose example, `.env.example`, README
- Add schema guidance and upgrade/restart notes
- Depends on: stable implementation from prior phases
- Complete before release: deployment path documented and repeatable
- Milestone: project is ready for a practical operator to deploy

## 10. Risks, Assumptions, and Open Decisions

### Risks
- **External API contracts may change without notice.** This affects adapter stability and mapping maintenance.
- **Provider-specific OAuth/token refresh may be fragile.** This can complicate one-provider-to-many-provider extensibility.
- **Rate limits may be tighter than expected.** This affects sync duration, retry behavior, and schedule design.
- **User changes to Grist schema may break imports.** This creates runtime failures unless validation is explicit.
- **Weak dedupe key strategy could cause duplicate or incorrect imports.** This is a core data integrity risk.
- **Large backfills may stress low-resource hosts.** This affects batching, memory usage, and state checkpointing.
- **Silent source-side corrections may be hard to reconcile.** This affects update strategy and repeated sync behavior.

### Assumptions
- **Grist is already deployed and reachable from the connector container.** Required for integration and deployment design.
- **Operator has valid source API credentials.** Without this, source connectivity cannot be validated.
- **Operator can create and maintain Grist tables.** The connector depends on expected target tables.
- **Source transaction/record IDs are stable enough for deduplication.** Core assumption behind idempotent sync.
- **Docker or equivalent container runtime is available.** Required for the target deployment model.
- **Initial use case is personal/small-scale finance import, not enterprise ingestion.** Supports simpler operational assumptions.

### Open decisions
- **Implementation stack choice: Python or Node.js.** Matters for library selection, scheduling approach, and test tooling.
- **Initial state store choice: local files, SQLite, or Grist tables.** Affects persistence robustness, deployment simplicity, and recovery handling.
- **Default write pattern: raw table first vs direct transaction import.** Impacts safety, traceability, and schema guidance.
- **Manual trigger mechanism: CLI only, HTTP endpoint, or both.** Affects runtime interface and deployment surface.
- **Scope of account/balance import in first version.** Transactions are clearly required; other object types depend on provider support.
- **Schema validation strictness against Grist tables at startup vs sync time.** Impacts operator experience and failure timing.

### Deferred items for later review
- **Two-way sync support.** Not part of current build and would materially alter architecture.
- **Webhook-driven imports.** Optional future enhancement beyond current polling/scheduling scope.
- **Web admin UI.** Not required and should not delay core connector delivery.
- **Expanded reconciliation logic beyond simple duplicate handling.** Out of current scope.
- **Category mapping logic inside connector.** Should remain in Grist unless explicitly approved.
- **Additional provider adapters beyond the first example implementation.** Architecture should support them, but they need not block the first delivery.

## 11. Builder Guardrails

- Do not write directly to Grist databases; use the Grist REST API only.
- Do not hardcode secrets in source code, example configs, or tests.
- Do not log API keys, tokens, refresh tokens, or other secret material.
- Do not mix provider-specific API logic into generic orchestration modules.
- Do not mark a sync as successful if Grist writes failed or required steps were incomplete.
- Do not update last successful sync state before successful completion of the intended sync.
- Do not treat retries/backoff as optional for transient provider failures.
- Do not collapse raw/staging import handling and processed transaction handling without explicit approval.
- Do not delete previously imported Grist data because of temporary source failures unless explicitly configured.
- Do not assume a single provider forever; keep extension points explicit.
- Do not bury operational failure details in code-only paths; surface them in logs/status.
- Do not skip dry-run support.
- Do not skip idempotency tests.
- Do not ship without documenting config, deployment, state persistence, and failure recovery behavior.

## 12. Definition of Ready for Coding

- Project scope is confirmed against the Functional Specification.
- Implementation stack is chosen.
- Initial provider for first implementation is chosen.
- State persistence approach is chosen and documented.
- Grist table strategy is confirmed:
  raw-first, direct import, or clearly staged hybrid.
- Required Grist document/table names and expected columns are confirmed.
- Deduplication key strategy is confirmed, including source namespacing.
- Duplicate handling modes to support in the first release are confirmed.
- Manual sync trigger method is agreed.
- Scheduler approach is agreed:
  internal, external, or both.
- Configuration model is agreed and split into runtime settings, install-time settings, and secrets.
- Deployment method is confirmed for the target environment.
- Health check behavior is defined.
- Logging format is agreed:
  human-readable, JSON, or both.
- Acceptance criteria are understood and traceable to tests.
- Mocking strategy and integration test environment are defined.
- Failure-handling expectations for partial writes and malformed records are agreed.
- README/documentation expectations are agreed.
- Any ambiguous items in Section 10 have explicit owner decisions or accepted assumptions.

## 13. Implementation Handoff Notes

For a developer or engineering team, the main priority is to keep the boundaries clean: provider adapters, transformation, dedupe/upsert planning, Grist API integration, and state persistence should remain separate from the start. The highest-risk areas are deduplication correctness, safe sync-state updates, partial failure handling, and Grist schema mismatch behavior.

For a coding agent such as Codex, the safest build order is: config validation, internal models/contracts, Grist client, state store, one provider adapter, transformation, dedupe, orchestrator, scheduler/health checks, then tests and deployment artifacts. The parts most likely to fail if guessed are the state-store choice, target Grist schema expectations, dedupe key details, and whether raw-table-first is mandatory or only recommended, so those should be treated as explicit assumptions unless confirmed.
