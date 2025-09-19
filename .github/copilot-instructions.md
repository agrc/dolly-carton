# Dolly Carton Development Instructions

**ALWAYS follow these instructions first and only fallback to additional search and context gathering if the information here is incomplete or found to be in error.**

## Project Overview

Dolly Carton is a Python CLI application that automatically syncs SGID (Statewide Geographic Information Database) geospatial data from the internal SGID database to ArcGIS Online. It runs as a GCP Cloud Run job triggered by the [AGOL Forklift pallet](https://github.com/agrc/warehouse/blob/main/sgid/~AGOLPallet.py) and serves as an automated data pipeline for publishing Utah's authoritative geographic data.

### What the Application Does
1. **Change Detection**: Compares table hashes from `SGID.Meta.ChangeDetection` with stored hashes in Firestore (prod/staging) or dev mocks
2. **Data Processing**: Creates file geodatabases containing only changed tables for efficient updates
3. **Publishing**: Updates existing feature services or publishes new ones to ArcGIS Online
4. **State Management**: Persists table hashes only after successful operations for reliable retry semantics

## Tech Stack & Dependencies

### Core Technologies
- **Python 3.12** - Primary language
- **GDAL 3.11.3** - Geospatial data processing (CRITICAL: Only available via Docker)
- **Docker** - Required for GDAL support and consistent deployment
- **ArcGIS Python API** - ArcGIS Online integration
- **Google Cloud Firestore** - State management for prod/staging
- **Firebase Emulator** - Local Firestore development
- **Microsoft SQL Server** - Internal database connectivity via ODBC Driver 18

### Key Python Libraries
- `arcgis==2.*` - ArcGIS Online API client
- `google-cloud-firestore==2.*` - Firestore integration
- `pyodbc==5.*` - SQL Server database connectivity
- `typer==0.*` - CLI framework
- `osgeo` (GDAL Python bindings) - Geospatial data manipulation
- `pytest==8.*`, `ruff==0.*` - Testing and code quality

### Development Environment Requirements
- **Docker is ABSOLUTELY REQUIRED** - Application cannot run without Docker due to GDAL dependency
- VS Code with Remote-Containers extension for optimal development experience
- The application WILL NOT work with direct Python installation

## Project Structure
```
├── src/dolly/              # Main application source
│   ├── main.py            # CLI entry point and orchestration
│   ├── agol.py            # ArcGIS Online integration
│   ├── internal.py        # Internal database operations
│   ├── domains.py         # GIS domain management
│   ├── state.py           # Firestore state management
│   ├── summary.py         # Process reporting and Slack integration
│   ├── utils.py           # Utility functions (Docker-independent)
│   ├── dev_mocks.json     # Development test data
│   └── secrets/           # Configuration files (gitignored)
├── tests/                 # Test suite (most require Docker)
├── output/                # Generated geodatabases and artifacts
├── scripts/               # Utility scripts (seed_table_hashes.py)
├── .devcontainer/         # VS Code dev container configuration
├── .github/workflows/     # CI/CD pipelines
└── Dockerfile             # Multi-stage build (base, dev_container, test, prod)
```

## Development Setup

### Bootstrap Process
1. **Open in VS Code dev container** (REQUIRED):
   - Open project in VS Code
   - Select "Reopen in Container" when prompted
   - Automatically builds `dev_container` Docker target with all dependencies

2. **Create secrets file** (required):
   ```bash
   cp src/dolly/secrets/secrets_template.json src/dolly/secrets/secrets.dev.json
   ```

3. **Environment is pre-configured** in dev container:
   - Python dependencies auto-installed via `pip install -e .[tests]`
   - Firebase emulator auto-starts on shell startup via `.zshrc`
   - `APP_ENVIRONMENT=dev` environment variable set
   - GDAL library available and configured
   - Oh My Zsh with autosuggestions for better terminal experience

### Environment Variables & Configuration
- `APP_ENVIRONMENT`: Controls runtime behavior (`dev`, `staging`, `prod`)
- `FIRESTORE_EMULATOR_HOST=127.0.0.1:8080`: Local Firestore emulator endpoint
- `GOOGLE_CLOUD_PROJECT=demo-test`: Development project identifier

## Build and Testing

### Docker Build Process
- **Build test image**:
  ```bash
  docker build --target test -t dolly-carton:test .
  ```
  - **CRITICAL**: Takes 1-5 minutes depending on network. NEVER CANCEL. Set timeout to 30+ minutes.
  - Downloads Microsoft ODBC Driver 18 for SQL Server
  - Includes SSL workarounds for CI environments with self-signed certificates
  - Uses Ubuntu 24.04 base with GDAL 3.11.3 full support

- **Run full test suite**:
  ```bash
  docker run --rm -v $PWD:/workspace -w /workspace dolly-carton:test pytest
  ```
  - Takes 5-15 seconds to run. Set timeout to 10+ minutes for safety.
  - Includes coverage reporting (target: auto, threshold: 1%)

### Testing Strategy
- **Limited tests without Docker** (utils and summary modules only):
  ```bash
  APP_ENVIRONMENT=dev pytest tests/test_utils.py tests/test_summary.py -v
  ```
  - These modules have no GDAL dependency
  - All other test modules REQUIRE Docker to run
- **CI/CD Testing**: Pull requests trigger full Docker-based test suite with linting via GitHub Actions

### Code Quality Tools
- **Format code**: `ruff format .` (takes <1 second)
- **Check linting**: `ruff check .` (takes <1 second)
- **ALWAYS run these before committing** or CI will fail
- VS Code auto-formats on save using Ruff extension

## Application Architecture

### Change Detection System
- **Production**: Firestore document stores table name → hash mappings
- **Development**: `src/dolly/dev_mocks.json` simulates changed tables with fake hashes
- **Table Processing**: Only tables with hash mismatches are processed
- **Retry Logic**: Failed tables retain old hashes and retry on next run

### Data Flow
1. Query current hashes from `SGID.Meta.ChangeDetection`
2. Compare with stored hashes (Firestore or dev mocks)
3. Create file geodatabases for changed tables
4. Upload and publish/update to ArcGIS Online
5. Update stored hashes only after successful operations

### Key Modules
- **main.py**: CLI orchestration with Typer, process timing, error handling
- **internal.py**: SQL Server connectivity, GDAL operations, domain handling
- **agol.py**: ArcGIS Online publishing, feature service management
- **state.py**: Firestore state management with environment-specific logic
- **summary.py**: Process reporting with Slack integration and GCP logs links
- **utils.py**: Shared utilities (secret management, retry logic, GUID validation)

## CLI Commands

### Main Commands (Reference Only - Agents Should NOT Run)
```bash
# Process all changed tables
dolly

# Process specific tables
dolly --tables "sgid.society.cemeteries,sgid.boundaries.municipalities"

# Clean up dev environment AGOL items
dolly-cleanup-dev-agol
```

## Agent Validation Requirements

### Before Committing
1. **Format and lint code**: Always run `ruff format .` and `ruff check .`
2. **Run test suite**: `pytest -v`
3. **Verify changes**: Use git diff to confirm only intended changes

### What Agents Should NOT Do
- Run `dolly` application commands

## Troubleshooting & Common Issues

### Docker & Environment Issues
- **"Module not found 'osgeo'" Error**: Trying to run outside Docker container → Use dev container
- **Docker build in CI environments**: SSL workarounds are included for self-signed certificates
- **Firebase emulator not starting**: Should auto-start via `.zshrc` → Check with `nc -z 127.0.0.1 8080`
- **"metadata.google.internal" firewall warning**: Normal when running locally → Safe to ignore

### Build & Deployment
- **Multi-stage Dockerfile**:
  - `base`: Ubuntu 24.04 + GDAL 3.11.3 + ODBC Driver 18
  - `dev_container`: Adds Node.js 22, Firebase tools, Zsh with Oh My Zsh
  - `test`: Copies code and installs test dependencies
  - `prod`: Production runtime image
- **GCP Deployment**: Cloud Run job with shared VPC networking
- **Memory requirements**: Recent commits show memory bumps for large data processing

### Development Environment Details
- **Auto-configured ports**: 8080 (Firestore), 4000 (Firebase UI), 4400 (Firebase Hub)
- **Shell setup**: Zsh with autosuggestions, history persistence via volume mount
- **VS Code extensions**: Ruff, Python, Docker, Coverage Gutters, Code Spell Checker
- **Python interpreter**: `/usr/local/bin/python` in container

## Important File Locations

### Configuration & Secrets
- `src/dolly/secrets/secrets_template.json` - Template for all environments
- `src/dolly/secrets/secrets.dev.json` - Local development (create from template)
- `src/dolly/dev_mocks.json` - Mock data simulating changed tables
- `firebase.json` - Firestore emulator configuration
- `codecov.yml` - Code coverage settings (target: auto, threshold: 1%)

### Key Source Files
- `src/dolly/main.py` - CLI entry point with Typer, orchestrates entire process
- `src/dolly/agol.py` - ArcGIS Online integration (619 lines)
- `src/dolly/internal.py` - Database operations and GDAL processing
- `src/dolly/state.py` - Firestore state management with environment detection
- `src/dolly/utils.py` - Docker-independent utilities (testable without GDAL)

### CI/CD & Scripts
- `.github/workflows/` - Push, PR, release workflows with Docker builds
- `scripts/seed_table_hashes.py` - Production utility for Firestore hash seeding
- `.devcontainer/devcontainer.json` - Complete dev environment specification

## Code Style & Patterns

### Python Code Guidelines
- **Ruff formatting**: Auto-format on save, run before commits
- **Type hints**: Use throughout codebase for better clarity
- **Error handling**: Comprehensive exception handling with process continuation
- **Retry logic**: Built-in retry decorator for network operations
- **Logging**: Structured logging with context-aware messages

### Testing Patterns
- **Pytest-style classes**: No unittest.TestCase inheritance
- **Mock usage**: Extensive use of pytest-mock for external dependencies
- **Environment isolation**: Tests use fake secrets and mocked external calls
- **Coverage**: Branch coverage with XML output for Codecov integration

### Domain-Specific Patterns
- **GIS data handling**: GDAL operations wrapped with proper error handling
- **Service naming**: Uses open-sgid conventions for service and table names
- **Geometry types**: Handles POINT, POLYGON, POLYLINE, and STAND ALONE tables
- **Change detection**: Table-level hashing with reliable retry semantics

## Conventional Commits & Releases

The project uses automated releases via GitHub Actions with these commit types:

### Release-Triggering Types
- `feat`: New features → Minor release → Features section
- `fix`: Bug fixes → Patch release → Bug Fixes section
- `docs`: Documentation → Patch release → Documentation section
- `deps`: Dependencies → Patch release → Dependencies section

### Non-Release Types
- `chore`, `ci`, `perf`, `refactor`, `test`: No release or changelog entry

## Maintaining These Instructions

**IMPORTANT**: When working on tasks, if you receive feedback, learn something new about the project, discover workarounds, encounter errors not covered here, or are told information that would be helpful for future work, you MUST offer to update these instructions by saying:

> "This seems like valuable information that would help future development. Should I add this to the copilot instructions?"

### When to Update Instructions
- **New workarounds discovered** for common problems
- **Updated build processes** or dependency changes
- **New testing patterns** or validation requirements
- **Environment setup issues** and their solutions
- **Project-specific conventions** not previously documented
- **Tool versions** or configuration changes
- **Any feedback** that changes how development should be done

### How to Update
1. Read current instructions to understand existing content
2. Propose specific addition/modification with clear reasoning
3. Update relevant section maintaining consistent formatting
4. Test that instructions still work with any new requirements
5. Commit with conventional commit message (usually `chore:` type)

This ensures the instructions remain current and helpful for all future development work.

## Workflow Summary
1. **Open in VS Code dev container** (Docker required)
2. **Create secrets.dev.json** from template
3. **Make code changes** following established patterns
4. **Format & lint**: `ruff format .` && `ruff check .`
5. **Test locally**: Run test suite for validation `pytest -v`
6. **Commit with conventional commit message**
7. **CI handles**: Full Docker build, test suite, and deployment
