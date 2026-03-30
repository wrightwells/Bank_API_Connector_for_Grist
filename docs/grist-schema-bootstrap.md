# Grist Schema Bootstrap Guidance

This connector currently writes account rows, space rows, transaction rows, and import log rows.

## Minimum Tables

### `Raw_Import_Transactions`

Create a table named `Raw_Import_Transactions` with these columns:

| Column | Suggested type | Required by connector | Notes |
|---|---|---|---|
| `external_id` | Text | Yes | Stable source record key used for deduplication |
| `source_name` | Text | Yes | Source/provider tag such as `starling_bank` |
| `transaction_date` | Date | Yes | Normalized transaction date |
| `description` | Text | Yes | Human-readable transaction description |
| `amount` | Numeric | Yes | Signed amount written as a decimal string |
| `currency` | Text | Yes | Source currency code |
| `account_id` | Text | Yes | Source account identifier |
| `external_reference` | Text | Yes | Source-side reference where available |

Recommended extra columns for operator workflows:

| Column | Suggested type | Notes |
|---|---|---|
| `imported_at` | DateTime | Can be filled by Grist formula or automation |
| `review_status` | Choice | Useful for manual review and reconciliation |
| `notes` | Text | Optional operator notes |
| `category` | Ref or Choice | Keep categorisation in Grist, not the connector |

## Import Log Table

### `Import_Log`

Create a table named `Import_Log` with these columns:

| Column | Suggested type | Required by connector |
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

## Spaces Table

### `Spaces`

Create a table named `Spaces` with these columns:

| Column | Suggested type | Required by connector | Notes |
|---|---|---|---|
| `space_id` | Text | Yes | Stable Starling savings goal/space identifier |
| `account_id` | Text | Yes | Source account identifier that owns the space |
| `source_name` | Text | Yes | Source/provider tag such as `starling_bank` |
| `space_name` | Text | Yes | Savings goal / space name |
| `space_balance` | Numeric | Yes | Current amount saved in the space |
| `space_target` | Numeric | Yes | Current target amount for the space |
| `space_transactions` | Numeric | Yes | Count of space-linked transactions observed in the fetched payload |

Assumption:
`space_transactions` is derived from the currently fetched Starling payload and may be `0` when Starling does not expose a direct transaction-to-space link in the returned records.

## Accounts Table

### `Accounts`

Create a table named `Accounts` with these columns:

| Column | Suggested type | Required by connector |
|---|---|---|
| `account_id` | Text | Yes |
| `source_name` | Text | Yes |
| `account_name` | Text | Yes |
| `currency` | Text | Yes |
| `account_type` | Text | Yes |

## Config Alignment

These environment variables must match your Grist document schema if you rename columns:

- `GRIST_TRANSACTIONS_TABLE`
- `GRIST_ACCOUNTS_TABLE`
- `GRIST_SPACES_TABLE`
- `GRIST_IMPORT_LOG_TABLE`
- `GRIST_EXTERNAL_ID_COLUMN`
- `GRIST_SOURCE_COLUMN`
- `GRIST_TRANSACTION_DATE_COLUMN`
- `GRIST_DESCRIPTION_COLUMN`
- `GRIST_AMOUNT_COLUMN`
- `GRIST_CURRENCY_COLUMN`
- `GRIST_ACCOUNT_ID_COLUMN`
- `GRIST_EXTERNAL_REFERENCE_COLUMN`
- `GRIST_ACCOUNT_NAME_COLUMN`
- `GRIST_ACCOUNT_TYPE_COLUMN`
- `GRIST_SPACE_ID_COLUMN`
- `GRIST_SPACE_NAME_COLUMN`
- `GRIST_SPACE_BALANCE_COLUMN`
- `GRIST_SPACE_TARGET_COLUMN`
- `GRIST_SPACE_TRANSACTIONS_COLUMN`

## Bootstrap Checklist

1. Create `Accounts`
2. Create `Spaces`
3. Create `Raw_Import_Transactions`
4. Create `Import_Log`
5. Confirm the connector env vars match the actual column names
6. Run the connector in `DRY_RUN=true`
7. Trigger `POST /sync`
8. Review logs and field mapping
9. Switch `DRY_RUN=false` when the output looks correct
