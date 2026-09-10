# API reference

Two prefixes, two auth types, kept structurally separate — neither surface
is ever reachable with the wrong credential type.

## Consumer-facing (`/api/v1`, auth: `X-API-Key` header)

### `POST /api/v1/memories`

```json
// request
{"namespace": "messages", "subject_id": "conv-42", "content": "The user prefers dark mode.", "metadata": {"role": "user"}}

// response 201
{"id": "b222b6d1-...", "namespace": "messages", "subject_id": "conv-42",
 "content": "The user prefers dark mode.", "metadata": {"role": "user"},
 "status": "active", "superseded_by_id": null,
 "created_at": "2026-08-31T02:28:49Z", "updated_at": "2026-08-31T02:28:49Z"}
```

Accepts an `Idempotency-Key` header — see
[10-latest-practices-checklist.md](./10-latest-practices-checklist.md).

### `POST /api/v1/memories/batch`

```json
// request
{"items": [{"namespace": "documents", "content": "chunk 1 text..."}, {"namespace": "documents", "content": "chunk 2 text..."}]}

// response 201
{"created": ["<uuid>", "<uuid>"], "failed": []}
```

One bad item doesn't fail the whole batch — `failed` lists
`{"index": N, "error": "..."}` for any item that errored.

### `POST /api/v1/memories/search`

```json
// request
{"namespace": "messages", "subject_id": "conv-42", "query": "does the user like dark mode", "top_k": 5}

// response 200
{"results": [
  {"id": "b222b6d1-...", "content": "The user prefers dark mode.", "metadata": {"role": "user"},
   "score": 0.68, "created_at": "2026-08-31T02:28:49Z"}
]}
```

`namespace` is required. `subject_id` is optional — omit it to search
across all subjects within that namespace for the application.

### `POST /api/v1/memories/{id}/supersede`

```json
// request
{"content": "The user has since switched to light mode."}

// response 201 — a NEW memory, the old one is retired (see 03-memory-data-model.md)
{"id": "<new-uuid>", "namespace": "messages", "content": "The user has since switched to light mode.", "status": "active", ...}
```

### `DELETE /api/v1/memories/{id}?hard=false`

`204 No Content`. Soft delete by default (marks `status: "deleted"`,
excluded from search, content retained); `hard=true` also calls the
adapter's `delete()` to remove the vector permanently.

### `GET /api/v1/memories/{id}`

Returns the memory regardless of status (including `superseded`/`deleted`)
— this is the one read path that isn't filtered, useful for audit lookups.

### `GET /api/v1/namespaces`

```json
{"namespaces": ["documents", "messages"]}
```

Distinct namespaces this application has ever written to.

### `POST /api/v1/evaluations`

Runs one or more evaluation frameworks against the application's real,
currently-configured retrieval — see
[15-evaluation-frameworks.md](./15-evaluation-frameworks.md) for why
multiple frameworks run as a fan-out, not a single choice. Rate-limited
like every other consumer endpoint.

```json
// request
{"frameworks": ["native", "ragas"],
 "cases": [
   {"query": "does the user like dark mode", "namespace": "messages",
    "expected_memory_ids": ["b222b6d1-..."],
    "expected_context": "The user prefers dark mode."}
 ]}

// response 202 — report is null until the run completes; poll GET below
{"id": "<run-uuid>", "status": "pending", "frameworks": ["native", "ragas"],
 "report": null, "error": null, "created_at": "2026-08-31T02:28:49Z", "completed_at": null}
```

`ragas`/`deepeval` need a judge LLM configured on the application (admin
UI only, not settable through this endpoint) — a request naming them
without one configured still returns `202`; each case's framework result
comes back as `{"error": "no judge LLM configured for this application"}`
rather than failing the request. `expected_memory_ids` enables the
`native` framework's metrics; `expected_context`/`generated_answer` enable
`ragas`/`deepeval`'s. Omitting all three still runs the request but every
framework that needs at least one returns `{"skipped": "..."}` for that
case.

### `GET /api/v1/evaluations/{run_id}`

```json
// response 200 — status: pending | running | completed | failed
{"id": "<run-uuid>", "status": "completed", "frameworks": ["native", "ragas"],
 "report": {"cases": [
   {"query": "does the user like dark mode",
    "retrieved": [{"id": "b222b6d1-...", "content": "The user prefers dark mode.", "score": 0.87}],
    "results": {
      "native": {"precision_at_k": 1.0, "recall_at_k": 1.0, "mrr": 1.0},
      "ragas": {"context_precision": 0.92, "context_recall": 1.0}
    }}
 ]}, "error": null, "created_at": "2026-08-31T02:28:49Z", "completed_at": "2026-08-31T02:29:14Z"}
```

## Admin-facing (`/admin/api/v1`, auth: JWT Bearer)

### Auth

- `POST /admin/api/v1/auth/login` — `{email, password}` → `{access_token, refresh_token}`
- `POST /admin/api/v1/auth/refresh` — `{refresh_token}` → `{access_token}`
- `GET /admin/api/v1/auth/me` — the authenticated admin's own record

### Applications

- `POST /admin/api/v1/applications` — create (all three dropdown fields, see [02](./02-multi-tenancy-and-adapters.md); optional `judge_llm_*` fields, see [15](./15-evaluation-frameworks.md))
- `GET /admin/api/v1/applications` / `GET .../{id}` — list / detail
- `PATCH /admin/api/v1/applications/{id}` — update; a backend/model-changing patch returns a `warning` field
- `DELETE /admin/api/v1/applications/{id}` — soft-disable only (`is_active=false`), never a hard delete

### API keys

- `POST /admin/api/v1/applications/{id}/api-keys` — `{label}` → `{id, full_key, key_prefix, last_four, label}` (full_key shown once)
- `GET /admin/api/v1/applications/{id}/api-keys` — list (never includes `full_key`)
- `DELETE /admin/api/v1/applications/{id}/api-keys/{key_id}` — revoke

### Observability

- `GET /admin/api/v1/applications/{id}/logs?status=404&since=...&limit=50`
- `GET /admin/api/v1/applications/{id}/usage-summary?window=1h|24h|7d`
- `GET /admin/api/v1/health/backends` — per-application `adapter.health_check()` results
- `GET /admin/api/v1/applications/{id}/evaluations?limit=50` — list past evaluation runs
- `GET /admin/api/v1/applications/{id}/evaluations/{run_id}` — full run detail, same shape as the consumer-facing `GET /api/v1/evaluations/{run_id}` above

## System

- `GET /health` — liveness only, always 200 if the process is up
- `GET /ready` — checks control-plane DB connectivity, 503 if unreachable
