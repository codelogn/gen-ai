# The memory data model

## One table, not one per use case

`Memory` (`app/modules/memory/models.py`) is the single table every
application and every use case writes to:

| Column | Purpose |
|---|---|
| `id` | UUID — also the vector store's point/row key |
| `application_id` | tenant scope — every query is filtered by this |
| `namespace` | a logical grouping the **calling application** defines, e.g. `"messages"`, `"documents"` — this service never interprets it |
| `subject_id` | an opaque identifier for whatever entity within that app this memory belongs to (a conversation id, an end-user id) — a plain string, never a real foreign key, since it's another system's own identifier |
| `content` | the raw text that gets embedded — always retained here regardless of vector backend |
| `metadata` | free-form JSON, per-use-case structured data |
| `status` | `active` / `superseded` / `deleted` |
| `superseded_by_id` | self-referential FK — the correction chain (see below) |
| `source_ref` | an opaque traceability string the calling app can stash; never parsed here |
| `vector_backend_generation` | copied from the application's current generation at write time |

## Why one generic table

The premise of building this as *shared infrastructure* rather than a
one-off feature is that use cases not yet known will show up later. A
per-feature table (`app1_conversation_messages`, `app2_support_tickets`,
...) means every new use case — including from applications that don't
exist yet — requires a schema migration in this service. `namespace` +
`metadata` absorb that variation without one: a brand-new consuming
application needs zero code changes here, only a registration
(`POST /admin/api/v1/applications`) and an API key.

**The honest tradeoff**: a generic `metadata` JSONB column loses
column-level type safety and query ergonomics that a purpose-built table
would have — `metadata->>'memory_type' = 'fact'` is slower and less
self-documenting than a real typed column, and nothing stops one
namespace's rows from having a wildly different `metadata` shape than
another's. This is acceptable at the scale this service is designed for.
The concrete signal to revisit it: a use case that needs an *indexed
numeric range query* (e.g. "all memories with a confidence score above
0.8") — JSONB expression indexes exist but are more awkward to reason
about than a plain typed column, and that's the point where a per-namespace
typed side-table might be worth the migration cost.

## Where the vector lives vs. where content lives

This is the single most important design decision in the schema, and it's
what makes backend-switching safe: `Memory` in the control-plane Postgres
database is **always** the system of record for content, metadata, and
lifecycle — regardless of which `vector_backend` the owning application
uses. The vector itself lives wherever the configured adapter puts it (a
SQLite file, a Postgres side-table, or a Qdrant collection — see
[04-vector-store-adapters.md](./04-vector-store-adapters.md)).

Practical consequence: deleting or corrupting a vector store is recoverable
(re-embed and re-upsert from `Memory.content`); losing the `memories` table
is not, since the vector stores hold no independently-readable text.

## The correction/supersede workflow

Rather than update-in-place or delete-and-recreate, correcting a memory
creates a **new** row and retires the old one:

```python
# app/modules/memory/service.py — MemoryService.supersede()
new_memory = await self.create(db, application, namespace=old.namespace,
                                content=new_content, subject_id=old.subject_id, ...)
old_memory.status = MemoryStatus.SUPERSEDED
old_memory.superseded_by_id = new_memory.id
await adapter.mark_inactive(application, old_memory.id)
```

This preserves a full audit trail — `GET /api/v1/memories/{old_id}` still
returns the retired content with `status: "superseded"` and
`superseded_by_id` pointing at its replacement — while `search()` excludes
it going forward, since every adapter's `query()` filters to active rows
only. Verified directly: superseding a memory and re-running the same
search query immediately drops the old content and surfaces the new one,
on all three storage backends.
