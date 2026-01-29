---
description: FastAPI route handlers and REST API endpoint guidelines
globs: ["**/api/endpoints/**/*.py", "**/api/routers/**/*.py", "**/routers/**/*.py"]
alwaysApply: false
---

# API Endpoints Guidelines

This directory contains FastAPI route handlers for all REST API endpoints.

## REST Best Practices

Follow RESTful conventions for all endpoints:

- **GET** - Retrieve resources (idempotent, no side effects)
- **POST** - Create new resources
- **PUT/PATCH** - Update existing resources
- **DELETE** - Remove resources
- Use plural nouns for resource names (`/projects`, `/jobs`, not `/project`, `/job`)
- Use path parameters for resource IDs: `/projects/{project_id}`
- Use query parameters for filtering, pagination, sorting
- Return appropriate HTTP status codes:
  - `200 OK` - Successful GET, PUT, PATCH, DELETE
  - `201 Created` - Successful POST
  - `204 No Content` - Successful DELETE with no response body
  - `400 Bad Request` - Invalid request data
  - `404 Not Found` - Resource not found
  - `409 Conflict` - Resource conflict (e.g., duplicate)
  - `422 Unprocessable Entity` - Validation errors

### API Versioning

Follow the established versioning scheme in router prefixes:
- `/api/v1/` - Stable production APIs
- `/api/v2/` - Newer stable version
- `/api/v2alpha1/` - Alpha/beta features under development

Don't mix versions within the same router. Mark endpoints as deprecated when introducing replacements:

```python
@router.get("/old-endpoint", deprecated=True)
async def old_endpoint(...):
    """Old endpoint (deprecated, use /new-endpoint instead)."""
```

## Customer-Facing Documentation

**CRITICAL:** Endpoint docstrings and schema field descriptions are automatically published in customer documentation.

### Endpoint Docstrings

Endpoint docstrings appear in the OpenAPI spec and customer-facing API documentation. Keep them **short and concise**:

```python
@router.get("/{job_id}")
async def get_parse_job(...) -> ParseResultResponse:
    """Retrieve parse job with optional content or metadata."""
    # ✅ GOOD: Short, clear, describes what the endpoint does
```

**DON'T:**
```python
async def get_parse_job(...) -> ParseResultResponse:
    """
    Retrieve parse job with optional expanded result data (text, markdown, items).

    This endpoint allows you to fetch parse job results with various options.
    You can include the actual content or just metadata. The metadata includes
    size information and presigned URLs for downloading results.
    """
    # ❌ BAD: Too verbose, redundant, explains implementation details
```

### Schema Field Descriptions

Field descriptions in Pydantic models (request/response schemas) are also customer-facing. Keep them **short and concise**:

```python
class ParseResultRequest(Base):
    include_text: bool = Field(
        default=False,
        description="Include plain text result in response",
        # ✅ GOOD: Clear and concise
    )

    expand: list[str] = Query(
        default_factory=list,
        description="Fields to include: text, markdown, items. Metadata fields include presigned URLs.",
        # ✅ GOOD: Lists options, mentions key behavior
    )
```

**DON'T:**
```python
class ParseResultRequest(Base):
    include_text: bool = Field(
        default=False,
        description="Include plain text result in response. This will fetch the text content from S3 and return it in the response body. If the content is large, you may want to use the metadata endpoint instead to get a presigned URL.",
        # ❌ BAD: Too long, explains implementation, suggests alternatives
    )
```

**Guidelines:**
- **Maximum ~10-15 words** for field descriptions
- State what it does, not how or why
- Avoid implementation details
- Don't explain request/response patterns (that's in API guides)
- Don't include examples in descriptions (use OpenAPI examples separately)

## OpenAPI Spec Synchronization

**IMPORTANT:** After making changes to endpoint signatures, request schemas, or response schemas, you **MUST** run:

```bash
make refresh_frontend_sdk
```

This command:
1. Regenerates the OpenAPI specification (`openapi.json`)
2. Updates the frontend SDK (`frontend/packages/api`)
3. Updates the Python client SDK (`llama-cloud`)
4. Ensures customer documentation stays in sync

**When to run:**
- ✅ Added/modified endpoint parameters
- ✅ Changed request/response schemas
- ✅ Updated field descriptions
- ✅ Added/removed endpoints
- ✅ Changed endpoint paths or HTTP methods

**You should run this command automatically** as part of your workflow when making API changes. The generated files will be included in your commit.

## Common Patterns

### Authentication & Authorization

All endpoints must include appropriate dependencies:

```python
@router.get("/resource")
async def get_resource(
    user: User = Depends(get_user),              # Authentication
    project: Project = Depends(validate_project), # Project access check
) -> ResponseModel:
    """Get resource."""
    # Implementation
```

### Query Parameters

Use FastAPI `Query()` for documentation:

```python
@router.get("/")
async def list_resources(
    limit: int = Query(default=10, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
) -> ListResponse:
    """List resources with pagination."""
    # Implementation
```

### Response Models

Always specify response models for OpenAPI generation:

```python
@router.get("/{id}", response_model=ResourceResponse)
async def get_resource(...) -> ResourceResponse:
    """Get resource by ID."""
    return response
```

Use `response_model_exclude_unset=True` for optional fields:

```python
@router.get("/{id}", response_model_exclude_unset=True)
async def get_resource(...) -> ResourceResponse:
    """Get resource by ID."""
    return response  # Only includes fields that were explicitly set
```

## Error Handling

Raise HTTPException with appropriate status codes. Let FastAPI exception handlers convert service exceptions globally (preferred):

```python
# Simple errors in endpoints
if not resource:
    raise HTTPException(status_code=404, detail="Resource not found")

# Let exception handlers convert service exceptions
return await service.get_job(job_id)  # Service raises ResourceNotFoundError, handler converts to 404
```

## Service Layer Architecture

**CRITICAL:** Endpoints should be **thin wrappers** around service layer business logic. All business logic, data manipulation, and orchestration belongs in `src/app/services_v2/`.

### Separation of Concerns

**API Endpoints (this directory) should ONLY:**
- ✅ Handle HTTP request/response
- ✅ Parse and validate request parameters
- ✅ Call service layer methods
- ✅ Transform service responses to API schemas (if needed)
- ✅ Handle HTTP-specific concerns (status codes, headers)

**Services (`src/app/services_v2/`) should handle:**
- ✅ Business logic and validation
- ✅ Data access via CRUD operations
- ✅ Orchestration of multiple operations
- ✅ External service calls (S3, RabbitMQ, etc.)
- ✅ Complex transformations
- ✅ Error handling and logging

### Pattern: Lightweight Endpoints

```python
# ✅ GOOD: Lightweight endpoint that delegates to service
@router.post("/")
async def create_parse_job(
    request: ParseJobCreateRequest,
    user: User = Depends(get_user),
    project: Project = Depends(validate_project),
) -> ParseJobResponse:
    """Create a new parse job."""
    parse_service = get_parse_service()

    return await parse_service.v2.create_parse_job(
        request=request,
        user_id=user.id,
        project_id=str(project.id),
    )
```

```python
# ❌ BAD: Business logic in endpoint
@router.post("/")
async def create_parse_job(
    request: ParseJobCreateRequest,
    db: AsyncSession = Depends(get_db),  # ❌ Don't inject database sessions
) -> ParseJobResponse:
    """Create a new parse job."""
    # ❌ Don't do database operations, external services, or transformations in endpoints
    job_orm = ParseJobORM(...)
    db.add(job_orm)
    await db.commit()
    return transform_data(job_orm)
```

### Using Services in Endpoints

**1. Get service instance using factory functions:**

```python
from src.app.services_v2.parse.service.parse_service import get_parse_service

@router.get("/{job_id}")
async def get_parse_job(
    job_id: str,
    user: User = Depends(get_user),
    project: Project = Depends(validate_project),
) -> ParseJobResponse:
    """Get parse job by ID."""
    parse_service = get_parse_service()

    return await parse_service.get_job(
        job_id=job_id,
        user_id=user.id,
        project_id=str(project.id),
    )
```

**2. Services handle all business logic:**

The service layer handles:
- Fetching data from database
- Checking permissions
- Validating business rules
- Calling external services
- Error handling with proper logging

**3. Pass through user/project context:**

```python
# Always pass user_id and project_id to services for:
# - Multi-tenant data isolation
# - Permission checks
# - Audit logging
return await service.operation(
    user_id=user.id,
    project_id=str(project.id),
    # ... other parameters
)
```

**Example - Convert query params to service request:**

```python
@router.get("/{job_id}/results")
async def get_parse_results(
    job_id: str,
    expand: list[str] = Query(default_factory=list),
    user: User = Depends(get_user),
    project: Project = Depends(validate_project),
) -> ParseResultResponse:
    """Get parse job results."""
    request = ParseResultRequest(
        include_text="text" in expand,
        include_markdown="markdown" in expand,
    )

    parse_service = get_parse_service()
    return await parse_service.v2.get_combined_parse_results(
        job_id=job_id,
        user_id=user.id,
        project_id=str(project.id),
        request=request,
    )
```

### When Endpoints Can Have Logic

**Acceptable in endpoints:**
- ✅ Simple parameter parsing (e.g., splitting comma-separated values)
- ✅ Building request objects from query params
- ✅ Converting between API and service schemas (if different)

```python
# ✅ Simple parsing logic is acceptable
def _parse_expand_parameter(expand: list[str]) -> list[str]:
    """Parse expand parameter that may contain comma-separated values."""
    result = []
    for item in expand:
        result.extend(item.split(","))
    return [x.strip() for x in result if x.strip()]
```

### Async and Database Sessions

**CRITICAL:** Always use `async def` for endpoints. Never inject `AsyncSession` dependencies directly - let services handle database access:

```python
# ❌ DON'T inject database sessions in endpoints
async def endpoint(db: AsyncSession = Depends(get_db)):
    result = await db.execute(...)  # Don't do this

# ✅ DO let services handle database access
async def endpoint():
    service = get_service()
    return await service.operation()  # Service manages db internally
```

This prevents session management issues and keeps endpoints thin.

### Long-Running Operations

For long-running operations (>30 seconds), **prefer Temporal workflows** over background tasks:

```python
# ✅ BEST: Long operation with Temporal (has resiliency if API crashes)
@router.post("/process")
async def start_processing(...) -> JobResponse:
    """Start processing job."""
    service = get_service()
    job = await service.create_job_with_temporal_workflow(...)  # Temporal handles execution
    return JobResponse(job_id=job.id, status="pending")

# ⚠️ OK: Background task for simpler cases (but no crash recovery)
@router.post("/notify")
async def send_notification(...) -> AcceptedResponse:
    """Send notification."""
    background_tasks.add_task(send_email, ...)
    return AcceptedResponse(status="accepted")

# ✅ Quick operation - return result synchronously
@router.get("/{id}")
async def get_resource(...) -> ResourceResponse:
    """Get resource."""
    return await service.get_resource(...)
```

**Why Temporal?** If the API crashes during processing, Temporal workflows automatically resume when the service restarts. Background tasks are lost on crash.

## File Organization

- Group related endpoints in the same file (e.g., `parsing_v2.py` for parse endpoints)
- Use a router per module: `router = APIRouter(prefix="/v2/parse", tags=["Parse"])`
- Keep endpoint handlers focused - delegate business logic to services
- Use helper functions (prefixed with `_`) for shared logic within the file
