# Security Policy

## Scope

This project is a personal hiking app and may process sensitive personal data locally.

## Sensitive Data Types

TrailBuddy may handle:
- GPS coordinates and route tracks
- Hiking dates and durations
- Free-text personal notes

Do not commit this data to source control.

## Public Repository Guidance

Before making the repository public:
1. Confirm no data files are tracked (GPX, SQLite, vector DB indexes).
2. Confirm no secrets are present (.env values, tokens, passwords, API keys).
3. If sensitive files were committed in the past, rewrite Git history to remove them.

## Safe Defaults

The repository is configured to ignore common local-sensitive paths and file types in .gitignore.

## Reporting

If you discover a security issue, report it privately to the maintainer before public disclosure.
