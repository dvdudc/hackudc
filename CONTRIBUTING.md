# Contributing to Black Vault

First off, thank you for considering contributing to Black Vault! It's people like you that make this tool better for everyone.

## Development Setup

1. **Prerequisites**: Python 3.10+ and `libmagic` installed on your system.
2. **Clone the repo**:
   ```bash
   git clone https://github.com/dvdudc/hackudc.git
   cd hackudc/src
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables**:
   ```bash
   cp .env.example .env
   # Add your GEMINI_API_KEY and OLLAMA_HOST
   ```

## Coding Standards

- **Formatting**: We use `black` for formatting and `flake8` for linting. Please ensure your code passes both before submitting a PR.
- **Type Hints**: Please use Python type hints wherever possible, especially for public functions and class methods.
- **Docstrings**: Document your functions concisely using standard Google or Sphinx docstyles.

## Running Tests

Tests are located in the `tests/` directory. Run them using pytest:
```bash
pytest
```
Please ensure all existing tests pass and add new tests for your features or bug fixes.

## Pull Request Process

1. Fork the repo and create your branch from `main`.
2. Prefix your branch name (e.g., `feature/awesome-new-feature` or `bugfix/fix-that-bug`).
3. Write your code, add tests, and ensure everything behaves consistently with the architecture.
4. Update the `CHANGELOG.md` and any relevant documentation (like the `README.md` or `docs/technical_documentation.md`).
5. Submit your PR and describe your changes. Provide as much context as possible.

## Commit Conventions

We loosely follow Conventional Commits:
- `feat:` A new feature
- `fix:` A bug fix
- `docs:` Documentation only changes
- `style:` Changes that do not affect the meaning of the code (white-space, formatting, etc)
- `refactor:` A code change that neither fixes a bug nor adds a feature
- `test:` Adding missing tests or correcting existing tests

## Code Review Expectations

Maintainers review PRs based on:
1. Architectural consistency (e.g. not breaking the separation of concerns).
2. Cleanliness of code and absence of security vulnerabilities.
3. Test coverage.

Looking forward to your contributions!
