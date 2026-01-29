---
description: Python stack rules (FastAPI, Temporal, RabbitMQ, Testing)
globs: ["**/*.py", "pyproject.toml", "requirements.txt"]
alwaysApply: true
---

# Python Stack Guidelines

## 1. Tooling & Package Management
- **Manager**: Use `uv` for all package and project management.
- **Commands**:
    - Install/Sync: `uv sync`
    - Run Tests: `uv run -- pytest`
    - Linting: `uv run make lint`
- **Dependencies**: Managed in `pyproject.toml` (via `uv`).
    - **Groups**: Use dependency groups (`dev`, `docs`) for development tools.
    - **Extras**: Use optional dependencies (`extras`) for integrations/features.
    - **Lock File**: Ensure `uv.lock` is up to date.

## 2. Architecture & Patterns
- **Class-Based Design**: Use classes for Services and Repositories. Follow **SOLID** principles.
    - **Single Responsibility**: Each class does one thing (e.g., `UserService`, `UserRepository`).
    - **Dependency Inversion**: Inject dependencies via `__init__`.
- **REST Architecture**:
    - **Resources**: Use nouns (e.g., `/users`, not `/getUsers`).
    - **Methods**: Use standard HTTP verbs (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`) correctly.
    - **Stateless**: No server-side session state for APIs.
- **Framework**: FastAPI for REST APIs.
- **Structure**:
    - `app/routers/`: Request handling (thin layer).
    - `app/services/`: Business logic (Class-based).
    - `app/repositories/`: Database interaction (Class-based).
    - `app/models/`: Internal domain models.
    - `app/schemas/`: Pydantic models for API I/O.
- **Dependency Injection**: Use `fastapi.Depends`.
- **Async**: Use `async def` for I/O-bound operations.

## 3. Code Quality & Style
- **Python Version**: 3.11+.
- **Formatting**: Adhere to PEP 8. Use `ruff` (via `uv`).
- **Type Hints**: strict typing required for all function arguments and return values. Use `typing.Optional`, `typing.List`, etc.
- **Docstrings**: Required for all public modules, classes, and functions (Google style).
- **Imports**: standard lib -> third party -> local. Absolute imports preferred.

## 4. FastAPI Specifics
- **Validation**: Use Pydantic V2 models.
- **Status Codes**: Explicitly set `status_code` (e.g., `201 Created` for POST).
- **Error Handling**: Raise `HTTPException` with specific status codes. Do not return error dicts manually.
- **Routers**: Use `APIRouter` with `prefix` and `tags`.

## 5. Temporal Workflows
- **Non-Determinism**: **NEVER** use `datetime.now()`, `random()`, or `uuid.uuid4()` inside workflows. Use `workflow.now()`, `workflow.random()`, `workflow.uuid4()`.
- **I/O**: No external API/DB calls in workflows. Use **Activities** for all I/O.
- **Inputs/Outputs**: Use `dataclasses` for workflow/activity inputs and results.
- **Version**: Version workflows using `workflow.patched()` for breaking changes.

## 6. RabbitMQ (Pika)
- **Durability**: Declare queues and messages as `durable=True` and `delivery_mode=Persistent`.
- **Reliability**: Use manual acknowledgments (`auto_ack=False`). Ack only after successful processing.
- **Channels**: Use separate channels for consuming and publishing.

## 7. Testing
- **Framework**: `pytest`.
- **Async**: Use `@pytest.mark.asyncio` for async tests.
- **Fixtures**: Use `conftest.py` for shared fixtures (DB, client).
- **Mocking**: Use `unittest.mock.patch` or `pytest-mock` to isolate external dependencies (AWS, 3rd party APIs).
- **Coverage**: Aim for high coverage on `services` and `utils`.

## 8. Security
- **Secrets**: **NEVER** hardcode secrets. Use `os.getenv` and `python-dotenv`.
- **Validation**: Validate all inputs at the boundary (Pydantic schemas).
- **Logging**: **NEVER** log sensitive data (passwords, tokens). Use structured logging.
