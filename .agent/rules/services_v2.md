---
description: Architecture implementation rules for services_v2 backend code
globs: backend/src/app/services_v2/**/*
---
# services_v2 Architecture

Service layer architecture patterns. All services MUST follow this structure.

## Quick Validation Checklist

**When reviewing/writing services_v2 code:**
- [ ] All CRUD methods have `project_id: str` parameter
- [ ] API schemas use Literal + Values (not Enums)
- [ ] Service has `__init__(self, crud: MyCRUD | None = None)`
- [ ] No database operations in service.py
- [ ] Factory function has `@lru_cache`
- [ ] Reads use `get_db_reader_if_none()`, writes use `get_db_if_none()`

**What goes where:**
- Database queries → `crud.py`, Business logic → `service.py`, Temporal workflows → `service.py`
- S3/external APIs → `utils.py`, Schema conversions → `api_utils.py`

## Reference Examples (Read These First)

- `services_v2/split/` - Complete implementation with all layers
- `services_v2/parse/` - Temporal integration, types.py pattern
- `services_v2/permissions/` - Comprehensive Literal + Values

## Directory Structure

```
services_v2/{service_name}/
├── crud.py          # Single table
├── crud/            # OR: Multiple tables
│   ├── entity_a_crud.py
│   └── entity_b_crud.py
├── service.py       # Business logic (REQUIRED)
├── schema.py        # Internal schemas (REQUIRED)
├── types.py         # Shared Literal + Values (optional, see parse/types.py)
├── api_schema.py    # Public API schemas (optional)
├── api_utils.py     # Schema conversions (optional)
└── utils.py         # Helpers (optional)
```

## CRUD Layer (`crud.py`)

Database operations only. Call SQLAlchemy directly.

**Pattern:**
```python
class MyEntityCRUD:
    @staticmethod
    def _build_schema_from_orm(orm: MyEntityORM) -> MyEntity:
        return MyEntity(id=orm.id, project_id=orm.project_id, ...)

    async def get_entity(self, db: AsyncSession | None, entity_id: str, project_id: str) -> MyEntity | None:
        query = select(MyEntityORM).where(
            MyEntityORM.id == entity_id,
            MyEntityORM.project_id == project_id  # CRITICAL: Always filter by project_id
        )
        async with postgres.get_db_reader_if_none(db) as db_session:  # Read = reader
            result = await db_session.execute(query)
            return self._build_schema_from_orm(result.scalar_one_or_none())

my_entity_crud = MyEntityCRUD()  # Module-level singleton
```

**Requirements:**
- ALWAYS enforce `project_id: str` in all methods (multi-tenant isolation)
- Static `_build_schema_from_orm()` for ORM → Pydantic conversion
- `get_db_if_none(db)` for writes, `get_db_reader_if_none(db)` for reads

## Service Layer (`service.py`)

Business logic. Orchestrates CRUD, Temporal workflows, other services.

**Pattern:**
```python
class MyEntityService:
    def __init__(self, crud: MyEntityCRUD | None = None) -> None:
        self._crud = crud or my_entity_crud  # Dependency injection

    async def create_entity(self, entity_create: MyEntityCreate, db: AsyncSession | None = None) -> MyEntity:
        # Business logic, validation here
        return await self._crud.create_entity(db=db, entity_create=entity_create)

    async def submit_workflow(self, entity: MyEntity, temporal_client: TemporalJobServiceClient):
        await temporal_client.my_entity.submit_workflow(
            workflow_id=entity.id, job_record=entity, project_id=entity.project_id
        )

@lru_cache
def get_my_entity_service() -> MyEntityService:
    return MyEntityService()
```

**Requirements:**
- Accept `crud` in `__init__()` for testability
- Make `db: AsyncSession | None = None` optional (pass for transactions)
- NEVER do database operations - delegate to CRUD

## Schema Layer (`schema.py`)

Internal schemas. Can use Enums (decoupled from API).

```python
class MyEntityStatus(str, Enum):  # Internal: Enums OK
    PENDING = "pending"

class MyEntity(BaseReadV2):
    status: MyEntityStatus
```

**Requirements:**
- MAY use Enums for internal type safety
- Inherit from `BaseReadV2`, use `PaginatedRequest[Filter]` / `PaginatedResponse[Entity]`

## API Schema Layer (`api_schema.py`)

Public API schemas. **CRITICAL:** Literal + Values only (NEVER Enums).

**Why?** Prevents API breaking changes, cleaner OpenAPI spec, no Enum serialization issues.

```python
MyEntityStatus = Literal["pending", "processing", "completed", "failed"]

class MyEntityStatusValues:  # Constants for type safety
    PENDING: MyEntityStatus = "pending"
    COMPLETED: MyEntityStatus = "completed"

    @classmethod
    def all(cls) -> list[str]:
        return [cls.PENDING, cls.COMPLETED]

class MyEntityResponse(BaseReadV2):
    status: MyEntityStatus  # Literal type

class MyEntityCreateRequest(BaseModel):
    entity_type: MyEntityType

    @field_validator("entity_type", mode="after")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        if v not in MyEntityTypeValues.all():
            raise ValueError(f"Invalid: {v}")
        return v
```

**Usage:** Always use constants: `MyEntityStatusValues.PENDING` not `"pending"`

## Conversion Layer (`api_utils.py`)

Transform API ↔ service schemas.

```python
def to_service_filter(api_filter: FilterRequest, project_id: str) -> ServiceFilter:
    data = api_filter.model_dump(exclude_unset=True) if api_filter else {}
    data["project_id"] = project_id  # CRITICAL: Always enforce
    return ServiceFilter.model_validate(data)

def to_service_create(request: CreateRequest, project_id: str, user_id: str):
    return ServiceCreate(
        project_id=project_id,
        user_id=user_id,
        entity_type=cast(EntityType, request.entity_type),  # Cast API str → internal Literal
    )
```

## Common Anti-Patterns

❌ **Service doing DB operations:**
```python
class MyService:
    async def create(self, db):
        await db.execute(select(MyORM)...)  # NO! Use CRUD
```

❌ **Missing project_id isolation:**
```python
async def get_entity(self, db, entity_id: str):  # NO! Missing project_id
    query = select(MyORM).where(MyORM.id == entity_id)
```

❌ **Raw strings instead of Values:**
```python
entity.status = "pending"  # NO! Use StatusValues.PENDING
```

❌ **API using Enums:**
```python
class MyEntityResponse(BaseReadV2):
    status: MyEntityStatus  # NO if MyEntityStatus is Enum! Use Literal
```

## Request Flow

API endpoint → `api_utils.to_service_*()` → Service → CRUD → Database

```python
# In app/api/endpoints/my_entity.py
@router.post("/")
async def create_entity(
    request: MyEntityCreateRequest,  # API schema
    project_id: str = Depends(get_project_id),
):
    service_create = to_service_create(request, project_id, user_id)
    entity = await get_my_entity_service().create_entity(service_create)
    return to_api_response(entity)
```

## Transaction Management

**Pass `db` only for multi-operation transactions:**
```python
async with postgres.get_db_ctxm() as db:
    entity_a = await service_a.create(create_a, db=db)
    entity_b = await service_b.create_related(entity_a.id, create_b, db=db)
    await db.commit()  # Both or neither
```

For single operations, let CRUD handle sessions.

## Auditing Existing Code

**Red flags:**
1. CRUD without `project_id` parameter → Add to all methods
2. API schema with Enum → Convert to Literal + Values
3. Service without `__init__(crud=None)` → Add dependency injection
4. DB operations in service.py → Move to CRUD
5. Raw strings like `"pending"` → Use `StatusValues.PENDING`
6. Missing `@lru_cache` → Add to factory function
7. Write using `get_db_reader_if_none()` → Change to `get_db_if_none()`
