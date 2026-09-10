# Vector store adapters

Three concrete implementations of `VectorStoreAdapter`
(`app/modules/vectorstore/`), deliberately built and sequenced from
simplest to most operationally involved.

## `SqliteVecAdapter` — simplest, no server

Uses the [sqlite-vec](https://github.com/asg017/sqlite-vec) extension's
`vec0` virtual table — a loadable SQLite extension, no separate process at
all. One file per application: `data/vectors/{slug}_g{generation}.db`.

```sql
CREATE VIRTUAL TABLE vectors USING vec0(
  memory_id TEXT PRIMARY KEY, embedding FLOAT[{dim}] distance_metric=cosine
);
CREATE TABLE vector_status (
  memory_id TEXT PRIMARY KEY, is_active INTEGER, namespace TEXT, subject_id TEXT
);
```

`vec0` tables are vector-only (no other columns), so a plain side table
(`vector_status`) carries `is_active`/`namespace`/`subject_id` for
filtering — see "Namespace filtering is mandatory" below. Query:

```sql
SELECT memory_id, distance FROM vectors WHERE embedding MATCH ? AND k = ? ORDER BY distance
```

No network hop, no connection pool, nothing to monitor as a separate
service. A genuinely useful option for a low-traffic application that
shouldn't need to depend on a database server at all.

## `PgvectorAdapter` — shares infrastructure with the control plane

A per-application table in the **same** control-plane Postgres database:
`memory_vectors_{slug}_g{generation}`, with a `vector(dim)` column, an HNSW
index for approximate nearest-neighbor search, and `namespace`/
`subject_id`/`is_active` columns for filtering.

```sql
CREATE TABLE memory_vectors_myapp_g1 (
  memory_id UUID PRIMARY KEY, embedding vector(768) NOT NULL,
  is_active BOOLEAN DEFAULT true, namespace TEXT DEFAULT '', subject_id TEXT
);
CREATE INDEX ... USING hnsw (embedding vector_cosine_ops);
```

Requires the `pgvector` Postgres extension. **One documented Alembic
exception**: these per-application tables are created dynamically at
runtime by `PgvectorAdapter.provision()`, not through an Alembic revision
— they're data-driven (one per application, on demand), not fixed schema.
Alembic's `autogenerate` will try to `DROP TABLE` them if it ever sees
them as "unexpected" — never let that generated line survive a migration
review; this was caught and stripped out during development.

## `QdrantAdapter` — genuinely new infrastructure

A per-application Qdrant collection: `app_{slug}_g{generation}`, cosine
distance, with a payload (`application_id`, `namespace`, `subject_id`,
`status`) so Qdrant's own filtering handles exclusion without a round trip
back to Postgres. The only adapter requiring a **separate server process**
— run as a native binary under its own systemd unit, not a container,
since this environment doesn't run Docker.

`mark_inactive()` is a real payload update here (`status: "inactive"`),
unlike the other two adapters where it's closer to a flag flip on an
already-queried-together side table — the interface hides this real
implementation-cost difference from every caller, which is the point of
the interface existing.

## Namespace filtering is mandatory, not optional

Every adapter's `query()` accepts a `filters` dict and **must** honor
`namespace`/`subject_id` keys before ranking/limiting to `top_k`. This was
a real bug caught during development: an early version queried each
backend's whole vector space (all namespaces mixed together) and filtered
by namespace only *after* fetching the KNN results — meaning a search
could silently return fewer than `top_k` valid results, or the wrong ones
entirely, whenever another namespace's content happened to be nearby in
embedding space. Fixed by pushing the namespace/subject_id filter down
into each adapter's actual query (a SQL `WHERE` clause for the two SQL
backends, a Qdrant payload `FieldCondition` for Qdrant) — verified by
reproducing the exact failure (two namespaces on one application, a query
that should only touch one of them) and confirming correct, complete
results on all three backends afterward.

## What "admin picks a backend" does operationally

Assigning a backend triggers `provision(application, dimension)` for that
adapter, creating the file/table/collection sized to the application's
`embedding_dimension` (auto-detected — see
[06-embedding-providers.md](./06-embedding-providers.md)). This can't
happen before the dimension is known.

## Switching backend: no live migration

Changing `vector_backend` (or `embedding_model`/`embedding_provider`, which
also changes dimension) bumps `vector_backend_generation` and resets
`embedding_dimension` to `None`, forcing a **fresh, empty store** to be
provisioned on the next write. The old store is left physically in place
— untouched, not deleted — but no longer read or written. The admin
API's response to a backend-changing `PATCH` includes an explicit
`warning` field, and the admin UI requires a confirmation step. This is a
documented limitation, not silent data loss: since `Memory.content` in
Postgres is always retained independent of backend
([03-memory-data-model.md](./03-memory-data-model.md)), a real migration
tool — if ever needed — is just "loop over active memories, re-embed,
re-upsert to the new backend," not a new export format. Not built in V1
because no application has yet needed to switch backends with real
production data already on it.

Verified directly: switching a populated `sqlite_vec` application to
`pgvector` returned an empty search result set immediately after the
switch (fresh store, zero rows), while the original `.db` file remained on
disk, unmodified, with all its original data.
