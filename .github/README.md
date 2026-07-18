# GitHub configuration

Repository-level GitHub automation and collaboration configuration.

## Documentation

- English: [README.md](README.md)
- Tiếng Việt: [README.vi.md](README.vi.md)

## Contents

- [`workflows/`](workflows/README.md): CI, scheduled ingest jobs, and manually dispatched feature jobs.

## Rules

- Workflows must preserve the separation between ingest, validation, feature computation, signals, and backtests.
- Secrets must be read from GitHub Actions secrets and must never be printed.
- Production writes must use explicit commands and bounded scope.
- Workflow changes should be tested through pull requests before merging into `dev`.

See the workflow-specific documentation for current schedules and commands.
