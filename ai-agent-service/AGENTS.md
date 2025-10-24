# Agent Guidelines

Welcome to the AI Agent Service repository. This file provides guidance for AI agents and contributors working on this project.

## General Workflow
- Always use `rg` for searching through the codebase; avoid `grep -R` and `ls -R`.
- Keep the git worktree clean. Commit only relevant changes with clear messages.
- If you modify or add code or documentation, run the test suite before committing.

## Testing
- Run tests with:
  ```bash
  pytest tests/
  ```
- Ensure all tests pass before creating a pull request.

## Style
- Follow existing code style and conventions. Adhere to PEP8 for Python code unless local conventions differ.

## Documentation
- Update documentation alongside code changes when applicable.
