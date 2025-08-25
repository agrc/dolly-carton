# Copilot Custom Instructions

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

## Tools and Commands
- Format Python code: `ruff format <file>`
- Run tests: `python -m pytest tests/`
- Check for lint issues: `ruff check <file>`
