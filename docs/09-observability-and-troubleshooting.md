# Observability & troubleshooting

## Why durable, not in-memory-only

Every authenticated request writes one row to `request_logs`
(`RequestLoggingMiddleware`, `app/modules/usage/middleware.py`) — this is
a deliberate choice over an in-memory-only trace buffer, because the whole
premise of a shared service is that the people debugging a failure (an
application team) are not the people who can see this process's memory.
The admin panel's "Logs & usage" tab reads directly from this table; it
survives restarts and answers "what happened an hour ago," not just "what's
happening right now."

## What gets recorded

```python
# RequestLog columns
application_id, request_id, method, path, status_code, latency_ms,
retrieval_strategy, vector_backend,   # which strategy/backend actually served THIS request
error_detail, created_at
```

`retrieval_strategy`/`vector_backend` are captured from the resolved
`Application` object at request time
(`get_current_application` stashes them on `request.state`, the middleware
reads them back) — not looked up again afterward. This matters: if an
admin changes an application's strategy between two requests, each
request's log row reflects what actually served *it*, not the
application's current config, which could have changed since.

`error_detail` is populated only for truly unhandled exceptions (a bug
that escapes FastAPI's normal exception handling) — ordinary 4xx responses
(401, 404, 429, validation errors) are handled before the middleware ever
sees them as an exception; their detail is already in the response body
the caller received.

## `/health` vs. `/ready`

```python
GET /health  -> always 200 if the process is up (liveness)
GET /ready   -> 503 if the control-plane DB is unreachable (readiness)
```

Verified directly: stopping the Postgres service made `/ready` return 503
immediately while `/health` continued returning 200 — orchestration or a
reverse-proxy health check can use this distinction to know "merely up"
apart from "can actually serve," which `/health` alone can't express.

## A worked debugging walkthrough

**Symptom**: an application reports "search is returning nothing."

1. `GET /admin/api/v1/applications/{id}` — confirm `is_active: true` and
   note the current `vector_backend`/`embedding_dimension`. If
   `embedding_dimension: null`, no write has ever succeeded for this
   application (dimension is set on first successful write) — the problem
   is upstream of search entirely.
2. `GET /admin/api/v1/applications/{id}/logs?status=500&limit=20` — look
   for `error_detail` on recent failures. A `ValueError` mentioning "no
   embedding" usually means the configured Ollama model isn't pulled, or
   an OpenAI key is missing/invalid.
3. `GET /admin/api/v1/health/backends` — confirms whether the configured
   backend itself is reachable, independent of any specific application's
   data.
4. `GET /admin/api/v1/applications/{id}/usage-summary?window=1h` — a
   sudden spike in `error_rate` correlated with a recent config change (the
   admin UI's edit history isn't tracked yet, but `updated_at` on the
   application row is a starting point) usually points at a backend/model
   switch that hasn't been followed by re-upserting data (see
   [04-vector-store-adapters.md](./04-vector-store-adapters.md)'s
   fresh-start-on-switch policy — this is the single most common
   "search returns nothing" cause).

No separate metrics stack (Prometheus, etc.) exists or is planned for V1
— at this scale, a SQL aggregation query
(`usage_service.usage_summary()`: `count`, `avg(latency_ms)`,
`percentile_cont(0.95)`, `error_rate`) answers "is this application
healthy" just as well, without operating a metrics stack nobody asked for.
