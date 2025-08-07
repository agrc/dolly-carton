# 🛒 Dolly Carton

[![codecov](https://codecov.io/gh/agrc/dolly-carton/branch/main/graph/badge.svg)](https://codecov.io/gh/agrc/dolly-carton)

Automated pipeline for syncing SGID data in internal to ArcGIS Online

## What it does

1. Queries for updated tables in internal using [SGID.Meta.ChangeDetection](https://github.com/agrc/cambiador)
2. Creates file geodatabases with updated tables
3. Publishes/updates ArcGIS Online feature services

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
