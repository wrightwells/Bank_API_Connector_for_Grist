# Implementation Steps

This guide is a practical runbook for deploying the connector when you:

- build the Docker image on a development machine
- copy the image to a server
- load and run it there

It also covers:

- what files to copy to the server
- how to run the container with Docker Compose
- how to reset persistence for a fresh start
- what to check if nothing seems to happen

## 1. Deployment Approach

Recommended deployment flow:

1. build the image on the development machine
2. export the image to a `.tar` file
3. copy the `.tar` file and required config files to the server
4. load the image on the server
5. run Docker Compose on the server using the loaded image

This is useful when:

- you do not want to build on the server
- you do not want to clone the full repo on the server
- you want predictable image versions

## 2. Build on the Development Machine

From the project directory on the development machine:

```bash
cd /home/ww/src/Bank_API_Connector_for_Grist
docker build -t grist-finance-connector:0.1.0 .
docker save grist-finance-connector:0.1.0 -o grist-finance-connector_0.1.0.tar
docker images | grep grist-finance-connector
```

Expected result:

- the image exists locally
- the tar file `grist-finance-connector_0.1.0.tar` exists

## 3. Files to Copy to the Server

Copy these to the server:

- `grist-finance-connector_0.1.0.tar`
- `docker-compose.yml`
- `.env`

Optional but useful:

- `docs/implementation-steps.md`
- `docs/grist-schema-bootstrap.md`
- `scripts/README.md`

Example copy command:

```bash
scp grist-finance-connector_0.1.0.tar user@server:/opt/grist-finance-connector/
scp docker-compose.yml user@server:/opt/grist-finance-connector/
scp .env user@server:/opt/grist-finance-connector/
```

## 4. Load the Image on the Server

On the server:

```bash
cd /opt/grist-finance-connector
docker load -i grist-finance-connector_0.1.0.tar
docker images | grep grist-finance-connector
```

Expected result:

- `grist-finance-connector:0.1.0` appears in the local Docker image list

## 5. Important Compose Detail

The repository now keeps a single Compose file: `docker-compose.yml`.

It includes both:

- `build:`
- `image:`

That works well when you run from the repository checkout.

If you are deploying from a preloaded tar image on a server, copy the repo files you need alongside `docker-compose.yml` and `.env`, then run the same Compose file there.

## 6. Start the Container on the Server

```bash
docker compose up -d
```

## 7. Verify the Container Is Running

```bash
docker ps
docker logs grist-finance-connector --tail 100
curl http://127.0.0.1:8080/health
```

Expected result:

- container is running
- health endpoint returns JSON with `"status": "ok"`

## 8. First Sync Test

For first deployment, use:

```env
DRY_RUN=true
SCHEDULER_ENABLED=false
RUN_SYNC_ON_STARTUP=false
```

Then manually trigger sync:

```bash
curl -X POST http://127.0.0.1:8080/sync
```

Check:

- response JSON
- container logs
- `Import_Log` rows in Grist

If the preview looks correct, switch to:

```env
DRY_RUN=false
```

Then recreate the container:

```bash
docker compose up -d --force-recreate
```

Run sync again:

```bash
curl -X POST http://127.0.0.1:8080/sync
```

## 9. Fresh Start / Reset Persistence

If you need a clean start, you must remove the persisted sync state.

### Current default persistence model

The current compose setup uses a named Docker volume:

```text
connector_state
```

Inside that volume, the SQLite file is:

```text
/data/state/connector.sqlite3
```

### Full reset using the Docker volume

Stop the container:

```bash
docker compose down
```

Find the volume:

```bash
docker volume ls | grep connector_state
```

Remove it:

```bash
docker volume rm <actual_volume_name>
```

Then start again:

```bash
docker compose up -d
```

### If you later switch to a host bind mount

If you replace the named volume with a host directory, then delete the SQLite file at the path mapped to:

```text
/data/state/connector.sqlite3
```

That is the file that stores:

- last successful sync state
- job history

## 10. Useful Files to Keep on the Server

At minimum:

- `docker-compose.yml`
- `.env`
- `grist-finance-connector_0.1.0.tar`

Useful extras:

- a copy of the schema guide
- a copy of this implementation guide
- notes with your chosen schedule and Grist document ID

## 11. Useful Things People Forget

### 1. The container needs Grist connection settings

Your `.env` must include:

```env
GRIST_BASE_URL=http://grist:8484
GRIST_DOC_ID=your_doc_id
GRIST_API_KEY=your_grist_api_key
```

### 2. The Grist tables must already exist

You need these tables:

- `Accounts`
- `Spaces`
- `Raw_Import_Transactions`
- `Import_Log`

### 3. Multi-token Starling setups are supported

If one token only sees one account, use:

```env
STARLING_ACCESS_TOKENS=token_one,token_two,token_three
```

### 4. Leave account filters blank unless you mean to restrict import

```env
STARLING_ACCOUNT_UID=
STARLING_ACCOUNT_UIDS=
```

### 5. Scheduler settings do nothing unless enabled

These must both make sense together:

```env
SCHEDULER_ENABLED=true
SOURCE_SCHEDULE=0 * * * *
```

### 6. Schedule is UTC

The internal scheduler currently runs on UTC.

### 7. Manual sync still works even when scheduling is disabled

```bash
curl -X POST http://127.0.0.1:8080/sync
```

### 8. Dry-run can look successful without writing rows

If:

```env
DRY_RUN=true
```

then:

- `Import_Log` can be updated
- fetched counts can be non-zero
- but transaction/account/space tables will not be written

## 12. Recommended First Production Settings

After testing:

```env
DRY_RUN=false
SCHEDULER_ENABLED=true
SOURCE_SCHEDULE=0 * * * *
RUN_SYNC_ON_STARTUP=false
```

## 13. Quick Command Summary

### Build on dev machine

```bash
docker build -t grist-finance-connector:0.1.0 .
docker save grist-finance-connector:0.1.0 -o grist-finance-connector_0.1.0.tar
```

### Load on server

```bash
docker load -i grist-finance-connector_0.1.0.tar
docker images | grep grist-finance-connector
```

### Start on server

```bash
docker compose up -d
```

### Manual sync

```bash
curl -X POST http://127.0.0.1:8080/sync
```

### View logs

```bash
docker logs -f grist-finance-connector
```

### Reset persistence

```bash
docker compose down
docker volume ls | grep connector_state
docker volume rm <actual_volume_name>
docker compose up -d
```
