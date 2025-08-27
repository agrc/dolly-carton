# Dolly Carton Development Instructions

**ALWAYS follow these instructions first and only fallback to additional search and context gathering if the information here is incomplete or found to be in error.**

Dolly Carton is a Python CLI application for syncing SGID geospatial data from internal databases to ArcGIS Online. It runs as a GCP Cloud Run job and requires GDAL (Geospatial Data Abstraction Library) which is only available via Docker containers.

## Working Effectively

### Prerequisites
- **Docker is REQUIRED** - This application cannot run without Docker due to GDAL dependency
- VS Code with Remote-Containers extension for development
- The application WILL NOT work with direct Python installation

### Bootstrap and Development Setup
1. **Open in VS Code dev container**:
   - Open project in VS Code
   - Select "Reopen in Container" when prompted
   - This automatically builds the `dev_container` Docker target with all dependencies

2. **Create secrets file** (required):
   ```bash
   cp src/dolly/secrets/secrets_template.json src/dolly/secrets/secrets.dev.json
   ```

3. **Environment is pre-configured** in dev container:
   - Python dependencies auto-installed via `pip install -e .[tests]`
   - Firebase emulator auto-starts on shell startup
   - APP_ENVIRONMENT=dev is set
   - GDAL library is available

### Build and Test
- **Build Docker test image**: 
  ```bash
  docker build --target test -t dolly-carton:test .
  ```
  - Takes 15-45 minutes depending on network. NEVER CANCEL. Set timeout to 60+ minutes.
  - May fail in restricted network environments due to Microsoft ODBC driver downloads
  
- **Run full test suite**: 
  ```bash
  docker run --rm -v $PWD:/workspace -w /workspace dolly-carton:test pytest
  ```
  - Takes 5-15 seconds to run. NEVER CANCEL. Set timeout to 30+ minutes for safety.

- **Run specific tests without Docker** (limited subset only):
  ```bash
  APP_ENVIRONMENT=dev pytest tests/test_utils.py tests/test_summary.py -v
  ```
  - Only works for utils and summary modules (no GDAL dependency)
  - Other test modules WILL FAIL without Docker

### Code Quality
- **Format code**: `ruff format .` (takes <1 second)
- **Check linting**: `ruff check .` (takes <1 second)
- **ALWAYS run these before committing** or CI will fail

### Application Commands (Reference Only)
**For reference only - agents should NOT run these commands**:
```bash
# Process all changed tables
dolly

# Process specific tables  
dolly --tables "sgid.society.cemeteries,sgid.boundaries.municipalities"

# Clean up dev environment AGOL items
dolly-cleanup-dev-agol
```

**Note**: These commands require GDAL and should only be run by human developers

## Validation Requirements

### Agent Testing Requirements
- **Format and lint code**: Always run `ruff format .` and `ruff check .` before committing
- **Run unit tests**: Execute `APP_ENVIRONMENT=dev pytest tests/test_utils.py tests/test_summary.py -v`
- **Verify changes**: Use git diff to confirm only intended changes were made

**Note**: Agents should NOT run dolly application commands. Unit tests and linting are sufficient for validation.

### CI Validation Steps
- **ALWAYS run** `ruff format .` and `ruff check .` before committing
- **Test builds pass**: The `.github/workflows/push.yml` runs the Docker test build
- **Unit tests pass**: CI runs the full test suite via Docker

## Build Time Expectations
- **NEVER CANCEL builds or long-running commands**
- **Docker build**: 15-45 minutes (network dependent) - Set 60+ minute timeout
- **Test execution**: 5-15 seconds - Set 30+ minute timeout for safety  
- **Code formatting/linting**: <1 second
- **CLI execution**: Varies by data volume, can take hours for full sync

## Common Issues and Solutions

### "Module not found 'osgeo'" Error
- **Cause**: Trying to run application outside Docker container
- **Solution**: Use VS Code dev container or Docker commands

### Docker Build Fails with SSL/Network Errors
- **Cause**: Restricted network preventing Microsoft ODBC driver download
- **Limitation**: Build only works in environments with full internet access
- **Documented**: This is a known limitation in some corporate/restricted environments

### Firebase Emulator Not Starting
- **In dev container**: Should auto-start via .zshrc configuration
- **Check**: `nc -z 127.0.0.1 8080` to verify emulator is running
- **Manual start**: `firebase emulators:start --only firestore --project demo-test`

## Important File Locations

### Key Source Files
- `src/dolly/main.py` - Main CLI application entry point
- `src/dolly/agol.py` - ArcGIS Online integration 
- `src/dolly/internal.py` - Internal database operations
- `src/dolly/utils.py` - Utility functions (testable without Docker)

### Configuration
- `src/dolly/secrets/secrets.dev.json` - Local development secrets (create from template)
- `src/dolly/dev_mocks.json` - Mock data for development testing
- `.devcontainer/devcontainer.json` - VS Code dev container configuration
- `Dockerfile` - Multi-stage build (base, dev_container, test, prod)

### Tests
- `tests/test_utils.py` - Utility tests (runnable without Docker)
- `tests/test_summary.py` - Summary tests (runnable without Docker)
- `tests/test_*.py` - Other tests require Docker due to GDAL dependency

## Code Formatting Guidelines

### Python Code Style
- **Always use ruff for code formatting** - Run `ruff format` on any modified Python files
- **Include newlines before return statements** - Add a blank line before all `return` statements for better readability
- **Follow existing project patterns** - Maintain consistency with the current codebase style
- **Top-level imports** - Place all imports at the top of the file
- **Use descriptive variable names** - Choose variable names that clearly convey their purpose and content. Avoid single-letter names and ambiguous terms.

### Testing Patterns
- **Use pytest-style test classes** - Do not inherit from `unittest.TestCase`
- **Use direct imports** - Prefer `from module import function` over `import module as alias` when testing specific functions
- **Include comprehensive test coverage** - Add tests for both success and failure scenarios
- **Ask before you write tests** - After writing new code, ask before writing tests to allow me to review the changes first

### Documentation
- **Clear docstrings** - Include parameter descriptions and note which parameters are primarily for testing purposes
- **Type hints** - Use type hints where appropriate for better code clarity
- **Don't touch the changelog** - The changelog for this project is generated automatically, don't touch it.

### General Guidelines
- **Present a plan first** - Before making changes, outline the intended modifications and their purpose.
- **Incremental changes** - Make changes in logical, reviewable chunks
- **Preserve backward compatibility** - Ensure existing functionality continues to work
- **Use dependency injection** - Design functions to accept optional parameters for testing
- **Don't mess with version numbers** - Version numbers are managed automatically.

## Conventional Commit Types

> **Reference:** Commit types are defined in the [AGRC Release Composite Action](https://github.com/agrc/release-composite-action)

### Release-Triggering Commit Types
| Type | Description | Release Impact | Changelog Section |
|------|-------------|----------------|-------------------|
| `feat` | A new feature | Minor | Features |
| `fix` | A bug fix | Patch | Bug Fixes |
| `docs` | Documentation updates | Patch | Documentation |
| `style` | Changes to the appearance of the project/UI | Patch | Styles |
| `deps` | A dependency update. Dependabot should be configured to use this prefix. | Patch | Dependencies |

### Non-Release Commit Types
The following commit message types are supported but will not trigger a release or show up in the changelog:

| Type | Description |
|------|-------------|
| `chore` | Any sort of change that does not affect the deployed project |
| `ci` | Changes to CI configuration files and scripts |
| `perf` | A code change that improves performance |
| `refactor` | A code change that neither fixes a bug nor adds a feature |
| `test` | Adding missing tests or correcting existing tests |

## Workflow Summary
1. **Open in VS Code dev container** (required for development)
2. **Create secrets.dev.json** from template
3. **Make your changes** to source code
4. **Run** `ruff format .` and `ruff check .` to ensure code quality
5. **Test changes** by running dolly commands in dev container
6. **Run relevant test suite** via Docker if making significant changes
7. **Commit and push** - CI will validate with full Docker build and test suite

## Repository Structure
```
├── src/dolly/           # Main application source
├── tests/               # Test suite (most require Docker)
├── .devcontainer/       # VS Code dev container config
├── Dockerfile           # Multi-stage Docker build
├── .github/workflows/   # CI/CD pipelines
└── scripts/             # Utility scripts
```
