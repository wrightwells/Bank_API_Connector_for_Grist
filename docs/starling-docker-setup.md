# Starling + Grist Docker Setup Guide

This guide explains how to run the connector with Docker, where to put your Starling access token, how to verify the Starling connection before any data is written into Grist, and how to prepare the Grist document.

## 1. What You Are Running

This repository currently provides:

- the connector source code
- a `Dockerfile` for building the connector image locally
- a `docker-compose.yml` for running the connector container

At the moment, this is **not** set up as a published GitHub Release image pipeline. That means:

- you should build the image locally from this repository
- or push your own built image to your own container registry later

Current expected workflow:

1. clone the repository
2. create `.env`
3. build with Docker Compose
4. test in dry-run mode
5. enable writes once the payload looks correct

## 2. Before You Make a Final Compose File

Before treating the deployment as final, these decisions should be settled:

### Required checks

- confirm the correct Starling access token type for your account
- confirm the Grist document already exists
- confirm the Grist API key works against that document
- create the required Grist tables and columns
- run at least one dry-run sync
- confirm the imported field mapping is acceptable
- confirm whether you want scheduled sync enabled immediately or only after manual validation

### Strongly recommended decisions

- decide where `.env` will live on the host
- decide whether port `8080` should be exposed only locally or on your LAN
- decide whether you want one Starling account only or all discovered accounts
- decide where Docker volumes will persist state
- decide whether you want to keep `DRY_RUN=true` for first deployment

## 3. Where the Starling Access Token Goes

Put the Starling token in your `.env` file.

Use these settings:

```env
SOURCE_PROVIDER=starling
SOURCE_NAME=starling_bank
STARLING_ACCESS_TOKEN=your_real_starling_token_here
```

If Starling requires one token per account, you can instead use:

```env
STARLING_ACCESS_TOKENS=token_for_account_1,token_for_account_2,token_for_account_3
```

Optional:

```env
STARLING_ACCOUNT_UID=optional_specific_account_uid
```

Or multiple explicit account filters:

```env
STARLING_ACCOUNT_UIDS=account_uid_1,account_uid_2
```

If `STARLING_ACCOUNT_UID` is blank, the connector will discover all accessible Starling accounts and import from each account's default category.

Do not hardcode the token in source code.
Do not commit `.env` to git.

### Helper command to print available Starling account UIDs

This repository includes a helper script:

```bash
python3 scripts/print_starling_accounts.py --env-file .env.starling
```

It reads:

- `STARLING_ACCESS_TOKEN`
- `STARLING_API_BASE_URL`

from the env file and prints:

- `accountUid`
- `defaultCategory`
- `accountType`
- `currency`

Use the printed `accountUid` value in:

```env
STARLING_ACCOUNT_UID=that_account_uid_here
```

### Helper command to preview normalized Starling transactions

This repository also includes a read-only transaction preview helper:

```bash
python3 scripts/preview_starling_transactions.py --env-file .env.starling --days 7 --limit 5
```

What it does:

- reads your Starling settings from the env file
- fetches transactions directly from Starling
- normalizes them using the same mapping logic as the connector
- prints sample transactions locally
- does not write anything to Grist

This is the safest way to verify:

- the token works
- the account selection is correct
- the amount sign looks right
- the description mapping looks reasonable
- the transaction date mapping is correct

## 4. Docker Setup Steps

### Step 1: Clone the repository

```bash
git clone <your-repo-url>
cd Bank_API_Connector_for_Grist
```

### Step 2: Create your environment file

```bash
cp .env.example .env
```

### Step 3: Edit `.env`

Minimum Starling + Grist settings:

```env
LOG_LEVEL=INFO
SERVICE_PORT=8080
SCHEDULER_ENABLED=false
RUN_SYNC_ON_STARTUP=false
ENABLE_MANUAL_SYNC_ENDPOINT=true

GRIST_BASE_URL=http://grist:8484
GRIST_DOC_ID=your_grist_doc_id
GRIST_API_KEY=your_grist_api_key
GRIST_TRANSACTIONS_TABLE=Raw_Import_Transactions
GRIST_IMPORT_LOG_TABLE=Import_Log

SOURCE_PROVIDER=starling
SOURCE_NAME=starling_bank
SOURCE_ENABLED=true
STARLING_API_BASE_URL=https://api.starlingbank.com
STARLING_ACCESS_TOKEN=your_real_starling_token_here
STARLING_ACCOUNT_UID=

IMPORT_LOOKBACK_DAYS=30
DUPLICATE_MODE=skip_existing
DRY_RUN=true
BATCH_SIZE=100

STATE_DB_PATH=/data/state/connector.sqlite3
RETRY_COUNT=3
RETRY_BACKOFF_MS=1000
API_TIMEOUT_MS=15000
```

### Step 4: Check Docker networking

If Grist is running in Docker too, the important part is that the connector container can resolve the hostname used in `GRIST_BASE_URL`.

Examples:

- If Grist is in the same Compose stack, `GRIST_BASE_URL` may be `http://grist:8484`
- If Grist is on another machine, use its reachable LAN URL
- If Grist runs directly on the host, use a host-reachable address that the container can access

### Step 5: Build and start the connector

```bash
docker compose up --build -d
```

### Step 6: Check health

```bash
curl http://localhost:8080/health
```

Expected result:

- JSON response
- `"status": "ok"`

## 5. How to Host the Image

### Option A: Build locally

This is the current supported path.

```bash
docker compose up --build -d
```

### Option B: Build and tag your own image

If you want to host it yourself:

```bash
docker build -t your-registry/grist-finance-connector:0.1.0 .
docker push your-registry/grist-finance-connector:0.1.0
```

Then update `docker-compose.yml` to use `image:` instead of `build:`.

### Option C: GitHub Release image

This repository does **not** currently include:

- a GitHub Actions image build workflow
- an automated GitHub Release
- a published container image

If you want release-based hosting later, the next step would be to add:

- CI build
- image tagging
- registry publishing
- release notes

## 6. How to Prove Starling Connectivity Before Pushing to Grist

The safest path is:

1. keep `DRY_RUN=true`
2. make sure the Grist tables already exist
3. run a manual sync
4. inspect logs and sync result
5. only then change `DRY_RUN=false`

### Manual sync test

```bash
curl -X POST http://localhost:8080/sync
```

Expected result in dry-run:

- HTTP response should return success if Starling and Grist are reachable
- response should show `fetched_count`
- response should show `dry_run: true`
- no rows should be written into `Raw_Import_Transactions`

### What proves the Starling connection is working

You want all of these:

- `/health` returns `status: ok`
- `POST /sync` returns `success: true`
- `fetched_count` is greater than zero or at least consistent with the account/date range
- container logs show a completed sync rather than auth or transport failure
- Grist row count stays unchanged while `DRY_RUN=true`

### Check logs

```bash
docker compose logs -f connector
```

Look for:

- sync started
- sync completed
- fetched count
- inserted/updated/skipped counts

### If you want an extra cautious test

Use:

```env
DRY_RUN=true
IMPORT_LOOKBACK_DAYS=3
SCHEDULER_ENABLED=false
RUN_SYNC_ON_STARTUP=false
```

This keeps the first live test small and manual.

## 7. How to Push Data Only After Validation

Once dry-run looks correct:

1. change `DRY_RUN=false`
2. restart the container
3. trigger `POST /sync` manually once
4. confirm rows appear in Grist
5. only then enable scheduling if desired

Restart:

```bash
docker compose up -d --build
```

## 8. Grist Spreadsheet Setup

You need a Grist document with at least these two tables:

- `Raw_Import_Transactions`
- `Import_Log`

### Table 1: `Raw_Import_Transactions`

Create these columns exactly unless you also change the matching env vars:

| Column | Type | Required |
|---|---|---|
| `external_id` | Text | Yes |
| `source_name` | Text | Yes |
| `transaction_date` | Date | Yes |
| `description` | Text | Yes |
| `amount` | Numeric | Yes |
| `currency` | Text | Yes |
| `account_id` | Text | Yes |
| `external_reference` | Text | Yes |

Recommended extra columns:

| Column | Type |
|---|---|
| `imported_at` | DateTime |
| `review_status` | Choice |
| `notes` | Text |
| `category` | Choice or Ref |

### Table 2: `Import_Log`

Create these columns:

| Column | Type | Required |
|---|---|---|
| `source_name` | Text | Yes |
| `start_time` | DateTime | Yes |
| `end_time` | DateTime | Yes |
| `duration_seconds` | Numeric | Yes |
| `fetched_count` | Numeric | Yes |
| `inserted_count` | Numeric | Yes |
| `updated_count` | Numeric | Yes |
| `skipped_count` | Numeric | Yes |
| `failed_count` | Numeric | Yes |
| `status` | Text | Yes |
| `message` | Text | Yes |

## 9. How to Find the Grist Document ID

Open your Grist document in the browser.

The document ID is the value in the URL after `/doc/`.

Example:

```text
https://your-grist-host/o/docs/docIdHere
```

Use `docIdHere` as `GRIST_DOC_ID`.

## 10. First End-to-End Validation Sequence

Use this order:

1. Create Grist tables
2. Set `DRY_RUN=true`
3. Start connector with Docker
4. Check `GET /health`
5. Run `POST /sync`
6. Check response and logs
7. Confirm no rows were written
8. Set `DRY_RUN=false`
9. Run `POST /sync` again
10. Confirm rows appear in `Raw_Import_Transactions`
11. Confirm a row appears in `Import_Log`
12. Enable scheduler only after this works

## 11. Suggested First Production Settings

After validation:

```env
SCHEDULER_ENABLED=true
SOURCE_SCHEDULE=0 * * * *
DRY_RUN=false
RUN_SYNC_ON_STARTUP=false
```

This gives you:

- hourly sync
- persistent state in Docker volume
- manual health and sync endpoints
- safe restart behaviour

## 12. What I Would Do Before Calling This Final

- validate your actual Starling token against the live API in dry-run mode
- confirm the Grist table names and column names exactly match config
- confirm the amount sign is correct for your Starling transaction direction expectations
- confirm duplicate handling mode is the one you want
- decide whether the HTTP port should remain exposed publicly or only locally
- decide whether to add auth in front of `/sync` if the service is reachable outside your private network

## 13. Current Limitations

- no published release image yet
- no automated GitHub release workflow yet
- no built-in Grist table creation automation yet
- current implementation writes transactions and import logs, not full account-table sync
- current multi-source support is still one source per service instance
