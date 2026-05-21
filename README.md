# TrailBuddy

** A personal hiking journal + AI trail co-pilot **
This project started out as a pet project for me to practice modern AI engineering and product ownership, while hoping that this turns into something that is actually helpful and which I will continue using.

Idea is to create a lightweight application to log hikes, GPX routes and lap times, as well as notes about what was great (or terrible) about a hike for an AI model to remember the hiking history and be able to have a *personalized* chat history.

## Privacy and Data Safety

TrailBuddy is designed to work with personal hiking data. That data can include exact GPS routes, hike timestamps, and personal notes.

For a public repository:
- Do not commit personal GPX files.
- Do not commit generated database files.
- Keep all local runtime data in ignored folders.

Ignored local data patterns are managed in [.gitignore](.gitignore).

## Local Data Paths

Runtime data is expected in local-only paths such as:
- data/
- app/data/

These paths are intentionally ignored by Git.

## Before Publishing

1. Verify no personal data files are tracked in Git.
2. Verify no secrets exist in code, docs, or config.
3. If sensitive files were ever committed, rewrite Git history before publishing.

