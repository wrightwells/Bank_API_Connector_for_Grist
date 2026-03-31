# Scripts README

This folder contains small helper scripts for validating Starling connectivity before running the full connector sync.

These scripts are read-only helpers.
They do not write data into Grist.

If you are keeping a reusable Grist document template for this project, store it in `templates/grist/`.

## Prerequisites

Before running the scripts:

1. create an env file, usually `.env`
2. set your Starling access token in that file
3. set `SOURCE_PROVIDER=starling`
4. make sure `python3` is installed

Minimum `.env` values:

```env
SOURCE_PROVIDER=starling
SOURCE_NAME=starling_bank
STARLING_API_BASE_URL=https://api.starlingbank.com
STARLING_ACCESS_TOKEN=your_real_starling_access_token
STARLING_ACCESS_TOKENS=
STARLING_ACCOUNT_UID=
STARLING_ACCOUNT_UIDS=

GRIST_BASE_URL=http://grist:8484
GRIST_DOC_ID=placeholder
GRIST_API_KEY=placeholder
```

If Starling requires a separate token per account, use:

```env
STARLING_ACCESS_TOKENS=token_for_account_1,token_for_account_2,token_for_account_3
```

In that case, you can leave `STARLING_ACCESS_TOKEN` blank.

Note:

- The helper scripts use the same config loader as the main app.
- `GRIST_BASE_URL`, `GRIST_DOC_ID`, and `GRIST_API_KEY` still need to exist in the env file even though these helper scripts do not write to Grist.

## Script 1: Print Starling Accounts

File:

```text
scripts/print_starling_accounts.py
```

Purpose:

- connect to Starling
- list available accounts
- print `accountUid`
- print `defaultCategory`
- help you choose a `STARLING_ACCOUNT_UID`

Run it with:

```bash
python3 scripts/print_starling_accounts.py --env-file .env
```

Expected output:

- one or more Starling accounts
- each account shows:
  - `accountUid`
  - `accountType`
  - `defaultCategory`
  - `currency`

Use the `accountUid` value in your env file if you want to restrict imports to one account:

```env
STARLING_ACCOUNT_UID=that_account_uid_here
```

If you leave `STARLING_ACCOUNT_UID` blank, the connector will try all discovered accounts.

## Script 2: Preview Normalized Starling Transactions

File:

```text
scripts/preview_starling_transactions.py
```

Purpose:

- fetch a small Starling transaction window
- normalize transactions the same way the connector does
- print sample rows before anything is written to Grist

Run it with:

```bash
python3 scripts/preview_starling_transactions.py --env-file .env
```

Example with custom window and sample size:

```bash
python3 scripts/preview_starling_transactions.py --env-file .env --days 7 --limit 5
```

Arguments:

- `--env-file`
  - env file to load, for example `.env`
- `--days`
  - how many days of Starling transactions to request
  - default: `7`
- `--limit`
  - how many normalized rows to print
  - default: `5`

What to check in the output:

- the connector can authenticate to Starling
- transactions are returned
- `transaction_date` looks correct
- `description` looks sensible
- `amount` sign looks correct
- `account_id` matches the account you expect

## Recommended Order

Use the scripts in this order:

1. run `print_starling_accounts.py`
2. choose whether to set `STARLING_ACCOUNT_UID`
3. run `preview_starling_transactions.py`
4. confirm the normalized output looks correct
5. then move on to connector dry-run with Docker

## Safe Example Workflow

```bash
cp .env.example .env
```

Edit `.env`, then run:

```bash
python3 scripts/print_starling_accounts.py --env-file .env
python3 scripts/preview_starling_transactions.py --env-file .env --days 7 --limit 5
```

If the output looks right, proceed to Docker dry-run:

```bash
docker compose up --build -d
curl http://127.0.0.1:8080/health
curl -X POST http://127.0.0.1:8080/sync
```

Related project file location:

- Grist template folder: `templates/grist/`

## Troubleshooting

### Missing STARLING_ACCESS_TOKEN

Make sure `.env` contains:

```env
STARLING_ACCESS_TOKEN=your_real_starling_access_token
```

### Wrong provider selected

Make sure `.env` contains:

```env
SOURCE_PROVIDER=starling
```

### No accounts returned

Check:

- the token is valid
- the token has access to the expected Starling account
- `STARLING_API_BASE_URL` is correct

### No transactions returned

Check:

- the selected account actually has transactions in the requested window
- increase `--days`
- remove `STARLING_ACCOUNT_UID` temporarily to test account discovery

## Security Notes

- Do not commit `.env`
- Do not pass the Starling token on the command line if you can avoid it
- Prefer `--env-file .env`
- Treat script output as sensitive financial data
