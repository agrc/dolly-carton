# 🛒 Dolly Carton

[![codecov](https://codecov.io/gh/agrc/dolly-carton/branch/main/graph/badge.svg)](https://codecov.io/gh/agrc/dolly-carton)

Automated pipeline for syncing SGID data in internal to ArcGIS Online

This is a GCP Cloud Run job that is kicked off from the [AGOL Forklift pallet](https://github.com/agrc/warehouse/blob/main/sgid/~AGOLPallet.py).

## What it does

1. Determines which tables have changed by comparing per-table hashes from `SGID.Meta.ChangeDetection` with previously stored hashes in Firestore (staging/prod) or dev mocks (dev)
2. Creates a single file geodatabase containing only the changed tables for service updates and a separate one for each newly published service
3. Publishes new feature services or updates existing ones in ArcGIS Online
4. Persists the new table hashes only after a successful publish/update so failed tables are retried on the next run

### Change Detection

Change detection is done at the table level using the `hash` column in `SGID.Meta.ChangeDetection`.

Staging / Production:
- A Firestore document maintains a map of table names to their last successfully published hash.
- Current hashes are queried; any mismatch (or missing entry) marks the table for processing.
- After a table finishes successfully its hash is written back; failed tables are left untouched and will be retried next run.

Dev:
- No Firestore writes. The file `src/dolly/dev_mocks.json` contains an `updated_tables` list that simulates which tables have “changed”. Deterministic fake hashes (e.g. `dev-hash-0`) are generated for testing logic.

CLI override:
- You can bypass automatic change detection with `--tables` to force specific tables to process. Their current hashes are then stored (staging/prod) after success.

Firestore structure (staging/prod):

```
Collection: dolly-carton
	Document: state
		table_hashes: {
			"sgid.society.cemeteries": "abc123",
			"sgid.transportation.roads": "def456",
			...
		}
```

This enables reliable retry semantics: only fully successful tables advance their stored hash.

## Setup

Open project in VS Code and select "Reopen in Container"

### Configuration

Create `src/dolly/secrets/secrets.dev.json` based on `src/dolly/secrets/secrets_template.json`

## Usage

```bash
# Process all changed tables
dolly

# Process specific tables
dolly --tables "sgid.society.cemeteries,sgid.boundaries.municipalities"

# Clean up the AGOL items created by the `dolly` command in the dev environment (both local and the dev GCP project). This is useful for resetting your AGOL state between runs.
dolly-cleanup-dev-agol
```

### Manually running production environment locally

Assuming that you have a `secrets.prod.json` file.

```bash
APP_ENVIRONMENT=prod dolly --tables sgid.environment.deqmap_lust,sgid.environment.tankpst,sgid.environment.uicfacility
```

## Development

Development environment is pre-configured with VS Code dev containers.

```bash
# All dependencies are pre-installed in the dev container

# Test
python -m pytest

# Format
ruff format . --write
```

## App Environments

`APP_ENVIRONMENT` is an indicator of what environment the code is running in. This is set in the Dockerfile or Github Actions.

- `dev`: Development environment (local)
- `staging`: Staging environment (GCP)
- `prod`: Production environment (GCP)
