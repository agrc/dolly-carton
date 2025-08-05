# dolly-carton

[![codecov](https://codecov.io/gh/agrc/dolly-carton/branch/main/graph/badge.svg)](https://codecov.io/gh/agrc/dolly-carton)

Pull data from SGID Internal and push to AGOL

## Features

### Geodatabase Domain Support

Dolly Carton now supports extracting and creating Esri geodatabase domains when creating File Geodatabases (FGDBs):

- **Coded Value Domains**: Extracts and recreates domains with code-value pairs
- **Range Domains**: Extracts and recreates domains with min/max value constraints  
- **Field Associations**: Automatically applies domain associations to the appropriate fields
- **Type Conversion**: Handles conversion between Esri and OGR field types (String, Integer, Double, etc.)

The domain functionality integrates seamlessly with the existing FGDB creation workflow, automatically:

1. Extracting domain definitions from the source geodatabase
2. Parsing XML domain definitions for both coded value and range types
3. Creating equivalent domains in the output FGDB using GDAL's domain APIs
4. Applying domain associations to fields that reference them

This ensures that data validation rules and pick lists are preserved when data is exported from SGID Internal.

## Development

### Testing
```bash
# Run tests with coverage
python -m pytest
```

Coverage reports are automatically generated and uploaded to [Codecov](https://codecov.io/gh/agrc/dolly-carton) on pull requests.

## Commands

### `dolly`

Runs the main Dolly Carton process. Run `dolly --help` for more information.

### `dolly-cleanup-dev-agol`

Cleans up the AGOL items created by the `dolly` command in the dev environment (both local and the dev GCP project). This is useful for resetting your AGOL state between runs.
