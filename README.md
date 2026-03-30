# Grist Finance API Connector

Self-hosted connector scaffolding for importing finance data from external APIs into a self-hosted Grist instance.

## Status

This repository now includes the first working implementation slice. It includes:

- an implementation preparation pack derived from the functional specification
- a Python connector service with clear module boundaries
- container and environment templates
- SQLite-backed sync state and job history
- a generic JSON HTTP provider adapter
- a concrete Starling Bank provider adapter
- Grist REST client integration
- manual sync and health HTTP endpoints
- basic sync orchestration and tests

It does not yet contain every planned extension from the specification, but the core service path is now implemented.

## Chosen Defaults for Initial Build

These choices were not fully fixed by the specification, so they are documented here as implementation assumptions:

- Language/runtime: Python 3.12
- Packaging: `pyproject.toml`
- State store default: SQLite in a mounted data directory
- Scheduling default: internal scheduler support, with room for external triggering later
- Import strategy default: raw-table-first using `Raw_Import_Transactions`
- Deduplication default: `(source_name, external_id)`

## Repository Structure

```text
docs/
  implementation-preparation-pack.md
src/
  grist_finance_connector/
    config/
    grist/
    logging/
    models/
    providers/
    scheduler/
    services/
    state/
    main.py
tests/
Dockerfile
docker-compose.yml
.env.example
pyproject.toml
```

## Planned Build Order

1. Validate the target Grist schema against the chosen tables
2. Add richer provider-specific adapters beyond the generic JSON example
3. Expand recovery and failure-path integration tests
4. Extend multi-source configuration
5. Harden scheduling and operational status output

## Local Development

1. Copy `.env.example` to `.env`
2. Fill in the Grist and provider settings
3. Run `docker compose up --build`
4. Check `GET /health`
5. Trigger `POST /sync` for a manual run

## Key Documents

- [Implementation Preparation Pack](./docs/implementation-preparation-pack.md)
- [Grist Schema Bootstrap Guidance](./docs/grist-schema-bootstrap.md)
- [Starling Docker Setup Guide](./docs/starling-docker-setup.md)
- [Scripts README](./scripts/README.md)

## Grist Tables Required

The connector now syncs three main data tables into Grist:

- `Accounts`
- `Spaces`
- `Raw_Import_Transactions`

The required `Spaces` columns are:

- `space_id`
- `account_id`
- `source_name`
- `space_name`
- `space_balance`
- `space_target`
- `space_transactions`

See [Grist Schema Bootstrap Guidance](./docs/grist-schema-bootstrap.md) for the full table setup.

## Production Deployment Files

- [Production Compose File](./docker-compose.prod.yml)
- [Starling Environment Template](./.env.starling.example)

## Starling Bank

To use Starling Bank as the source:

1. Set `SOURCE_PROVIDER=starling`
2. Set `SOURCE_NAME=starling_bank`
3. Use either:
   `STARLING_ACCESS_TOKEN` for a single-token setup
   or
   `STARLING_ACCESS_TOKENS` for a multi-token setup
4. Optionally set `STARLING_ACCOUNT_UID` or `STARLING_ACCOUNT_UIDS` if you want to limit imports to specific accounts

The connector will discover accounts through Starling, use each account's default category, and import feed items into the configured Grist transactions table.

Single-token example:

```env
STARLING_ACCESS_TOKEN=your_starling_token
STARLING_ACCESS_TOKENS=
STARLING_ACCOUNT_UID=
STARLING_ACCOUNT_UIDS=
```

If Starling requires one token per account, use:

```env
STARLING_ACCESS_TOKEN=
STARLING_ACCESS_TOKENS=token_one,token_two,token_three
STARLING_ACCOUNT_UID=
STARLING_ACCOUNT_UIDS=
```

The connector will merge accounts discovered across all supplied Starling tokens.

If you want to restrict imports after discovery, use one of:

```env
STARLING_ACCOUNT_UID=single_account_uid
```

or

```env
STARLING_ACCOUNT_UIDS=account_uid_one,account_uid_two
```

To print your available Starling `accountUid` values safely from your token:

```bash
python3 scripts/print_starling_accounts.py --env-file .env.starling
```

To preview a few normalized Starling transactions before connecting writes to Grist:

```bash
python3 scripts/preview_starling_transactions.py --env-file .env.starling --days 7 --limit 5
```

## Sync Scheduling

The sync schedule is controlled by environment variables read by the connector at startup.
It is not hardcoded in the Docker Compose file itself.

The Compose file only starts the container.
The connector process inside the container decides whether to run automatic syncs and how often to run them.

### The Two Main Settings

The main settings are:

```env
SCHEDULER_ENABLED=false
SOURCE_SCHEDULE=0 * * * *
```

### `SCHEDULER_ENABLED`

This turns the built-in scheduler on or off.

- `SCHEDULER_ENABLED=false`
  - automatic sync is disabled
  - the connector starts and waits
  - sync only happens when you manually call:
    ```bash
    curl -X POST http://127.0.0.1:8080/sync
    ```

- `SCHEDULER_ENABLED=true`
  - automatic sync is enabled
  - the connector checks the schedule continuously
  - when the current time matches the schedule, a sync runs automatically

### `SOURCE_SCHEDULE`

This is the cron-style schedule expression used by the internal scheduler.

Format:

```text
minute hour day-of-month month day-of-week
```

Examples:

- `0 * * * *`
  - every hour at minute 0
- `*/15 * * * *`
  - every 15 minutes
- `*/30 * * * *`
  - every 30 minutes
- `0 */2 * * *`
  - every 2 hours
- `0 */3 * * *`
  - every 3 hours
- `0 */6 * * *`
  - every 6 hours
- `0 0,6,12,18 * * *`
  - 4 times a day at 00:00, 06:00, 12:00, and 18:00 UTC
- `0 6,12,18,22 * * *`
  - 4 times a day at 06:00, 12:00, 18:00, and 22:00 UTC
- `0 6 * * *`
  - every day at 06:00
- `0 6,18 * * *`
  - every day at 06:00 and 18:00
- `0 9,13,17 * * *`
  - 3 times a day at 09:00, 13:00, and 17:00 UTC
- `0 8,12,16,20 * * *`
  - 4 times a day at 08:00, 12:00, 16:00, and 20:00 UTC
- `0 7 * * 1`
  - every Monday at 07:00 UTC
- `0 7 * * 1,4`
  - every Monday and Thursday at 07:00 UTC
- `0 1 * * *`
  - once a day at 01:00 UTC
- `30 22 * * *`
  - every day at 22:30

### Common Ready-to-Use Schedules

If you want a practical copy/paste value, these are good starting points:

#### Every hour

```env
SOURCE_SCHEDULE=0 * * * *
```

#### Every 2 hours

```env
SOURCE_SCHEDULE=0 */2 * * *
```

#### Every 4 hours

```env
SOURCE_SCHEDULE=0 */4 * * *
```

#### 4 times a day

```env
SOURCE_SCHEDULE=0 0,6,12,18 * * *
```

or, if you prefer daytime-heavy syncs:

```env
SOURCE_SCHEDULE=0 8,12,16,20 * * *
```

#### Twice a day

```env
SOURCE_SCHEDULE=0 6,18 * * *
```

#### Once a day

```env
SOURCE_SCHEDULE=0 6 * * *
```

#### Every 15 minutes

```env
SOURCE_SCHEDULE=*/15 * * * *
```

### Important Timezone Detail

The current internal scheduler uses UTC time.

That means:

- `0 6 * * *` means 06:00 UTC
- not necessarily 06:00 in your local timezone

If you want local-time behavior, you should calculate the equivalent UTC schedule when setting `SOURCE_SCHEDULE`.

### How This Relates to Docker Compose

The Compose file does not itself define the sync interval.
It only passes environment variables into the container.

For example, if your `.env.starling` contains:

```env
SCHEDULER_ENABLED=true
SOURCE_SCHEDULE=0 * * * *
```

then after the container starts, the app will run an hourly sync.

If your `.env.starling` contains:

```env
SCHEDULER_ENABLED=false
```

then the app will not auto-sync at all, even if `SOURCE_SCHEDULE` is present.

### Manual-Only Mode

This is the safest mode for initial testing.

Use:

```env
SCHEDULER_ENABLED=false
RUN_SYNC_ON_STARTUP=false
```

Then run sync manually:

```bash
curl -X POST http://127.0.0.1:8080/sync
```

This is recommended while:

- validating Starling access
- validating Grist tables
- checking dry-run output
- confirming multi-account behavior

### Automatic Sync Mode

Once manual syncs are working correctly, enable the scheduler:

```env
SCHEDULER_ENABLED=true
SOURCE_SCHEDULE=0 * * * *
RUN_SYNC_ON_STARTUP=false
```

Then recreate the container:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.starling up -d --force-recreate
```

### `RUN_SYNC_ON_STARTUP`

This setting is separate from the normal schedule.

- `RUN_SYNC_ON_STARTUP=false`
  - the container starts and waits for either:
    - a scheduled time
    - a manual `POST /sync`

- `RUN_SYNC_ON_STARTUP=true`
  - the connector runs one sync immediately when the container starts
  - after that, normal scheduling still applies if `SCHEDULER_ENABLED=true`

For most production use, keeping this `false` is safer.

### Recommended Settings

#### First live validation

```env
DRY_RUN=true
SCHEDULER_ENABLED=false
RUN_SYNC_ON_STARTUP=false
```

#### Normal home use

```env
DRY_RUN=false
SCHEDULER_ENABLED=true
SOURCE_SCHEDULE=0 * * * *
RUN_SYNC_ON_STARTUP=false
```

#### More frequent refresh

```env
DRY_RUN=false
SCHEDULER_ENABLED=true
SOURCE_SCHEDULE=*/15 * * * *
RUN_SYNC_ON_STARTUP=false
```

### How to Confirm Scheduling Is Working

1. Set:

```env
SCHEDULER_ENABLED=true
SOURCE_SCHEDULE=*/15 * * * *
```

2. Recreate the container:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.starling up -d --force-recreate
```

3. Watch logs:

```bash
docker logs -f grist-finance-connector
```

4. You should see `sync started` automatically when the schedule matches.

### Practical Summary

- Docker Compose starts the service
- `.env.starling` controls whether auto-sync is enabled
- `.env.starling` controls how often sync runs
- `POST /sync` always lets you trigger a manual sync regardless of schedule
- current scheduler timing is based on UTC

## Guardrails

- Do not write directly to Grist databases
- Do not hardcode secrets
- Do not log secret material
- Do not mix provider-specific logic into generic orchestration
- Do not mark sync success before required writes succeed
