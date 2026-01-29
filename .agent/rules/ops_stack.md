---
description: DevOps rules (Docker, Git, CI/CD)
globs: ["Dockerfile", "docker-compose*.yml", ".git*", "**/.gitignore"]
alwaysApply: false
---

# DevOps Stack Guidelines

## 1. Docker
- **Base Images**: Use slim/alpine variants (e.g., `python:3.11-slim`). Fix versions, avoid `latest`.
- **Multi-Stage**: Use multi-stage builds (`builder` -> `runtime`) to minimize image size.
- **User**: Run containers as a non-root user (create `appuser`).
- **Caching**: Copy `pyproject.toml` and `uv.lock` and install dependencies *before* copying source code.
- **Ignore**: Always use `.dockerignore` (exclude `.git`, `__pycache__`, `venv`, secrets).

## 2. Git
- **Commits**: Follow [Conventional Commits](https://www.conventionalcommits.org/):
    - `feat(scope): description`
    - `fix(scope): description`
    - `docs(...)`, `style(...)`, `refactor(...)`, `test(...)`, `chore(...)`.
- **Atomic Commits**: One logical change per commit.
- **Ignore**: Comprehensive `.gitignore` (Python, OS, IDE, Environment files).
- **Branches**: Feature branching (`feature/name`, `fix/issue`). Do not commit directly to `main`.
