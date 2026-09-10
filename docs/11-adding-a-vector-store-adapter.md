# Recipe: adding a fourth vector store adapter

Say you want to add, e.g., a Weaviate or Milvus adapter. Steps:

## 1. Implement `VectorStoreAdapter`

New file `app/modules/vectorstore/your_backend_adapter.py`:

```python
from app.modules.vectorstore.base import VectorMatch, VectorStoreAdapter

class YourBackendAdapter(VectorStoreAdapter):
    async def provision(self, application, dimension) -> None:
        """Create the per-application store. Must be idempotent — calling
        it again for an already-provisioned (application, generation) is a no-op."""
        ...

    async def upsert(self, application, memory_id, vector, payload) -> None:
        ...

    async def query(self, application, vector, top_k, filters=None) -> list[VectorMatch]:
        """filters may contain "namespace"/"subject_id" — apply them as an
        equality filter BEFORE ranking/limiting. This is not optional — see
        docs/04-vector-store-adapters.md's "Namespace filtering is mandatory" section."""
        ...

    async def mark_inactive(self, application, memory_id) -> None:
        ...

    async def delete(self, application, memory_id) -> None:
        ...

    async def health_check(self, application) -> bool:
        ...

_your_backend_adapter = YourBackendAdapter()

def get_your_backend_adapter() -> YourBackendAdapter:
    return _your_backend_adapter
```

Naming convention: derive collection/table/file names from
`application.slug` + `application.vector_backend_generation`
(`{slug}_g{generation}`), matching every existing adapter — this is what
makes the fresh-start-on-switch policy work uniformly.

## 2. Add the enum value

`app/modules/applications/models.py`:

```python
class VectorBackend(str, enum.Enum):
    SQLITE_VEC = "sqlite_vec"
    PGVECTOR = "pgvector"
    QDRANT = "qdrant"
    YOUR_BACKEND = "your_backend"  # add this
```

No migration needed for the enum itself — `vector_backend` is stored as a
plain `String(20)` column, not a Postgres native enum, specifically so
adding a value is a code change, not a schema migration.

## 3. Register in the factory

`app/modules/vectorstore/factory.py`:

```python
elif application.vector_backend == VectorBackend.YOUR_BACKEND:
    from app.modules.vectorstore.your_backend_adapter import get_your_backend_adapter
    return get_your_backend_adapter()
```

## 4. Add the admin UI dropdown option

`app/admin_ui/templates/application_form.html`:

```html
{% for opt in ["sqlite_vec", "pgvector", "qdrant", "your_backend"] %}
```

## 5. Verify

Run the exact same sequence used to validate every existing adapter:
register an application with the new backend, create several memories
with clearly distinct topics, search and confirm similarity-ranked
results, supersede one and confirm it drops out of search, then switch a
different application from an existing backend to yours and confirm the
old data is retained but excluded until re-upserted.
