# Dockerized databases (optional)

Postgres+pgvector and Qdrant, in containers, as an **alternative** to the
native systemd-managed services gen-ai actually uses in a typical
deployment (`backend/scripts/setup.sh` for Postgres,
`backend/scripts/install_qdrant.sh` for Qdrant). This folder does not
replace or migrate anything — it's here for whichever of these applies to
you:

- You don't have (or don't want to use) sudo access to install Postgres/
  Qdrant natively on this machine.
- You're setting up a throwaway environment for testing.
- You want a Postgres/Qdrant instance you can wipe and recreate freely,
  independent of anything else on the host.

If none of those apply — e.g. you're working on the same host gen-ai is
already deployed on — you almost certainly want the native setup
(`../backend/scripts/setup.sh`), not this.

## Why there's no sqlite-vec service here

Unlike Postgres and Qdrant, SQLite-vec isn't a server — it's a library
loaded directly against a local file
(`backend/data/vectors/{app}_g{generation}.db`), created automatically the
first time an application configured for the `sqlite_vec` backend writes
data. There's nothing to "start" for it; it's already available the moment
gen-ai's own Python process runs, no container or extra setup required.

## Using it

```bash
cp .env.example .env
# edit .env: set a real POSTGRES_PASSWORD

docker compose up -d
docker compose ps   # wait for both to show "healthy"
```

This starts Postgres on **port 5433** (not 5432) and Qdrant on **6343/6344**
(not 6333/6334) — deliberately different from the standard ports, so this
can run at the same time as the native services without a conflict, if you
ever need both.

Start just one service if that's all you need:

```bash
docker compose up -d postgres
# or
docker compose up -d qdrant
```

Wipe everything and start clean:

```bash
docker compose down -v
```

## Pointing gen-ai at these instead of the native services

If you genuinely want gen-ai's control-plane database to live here instead
of the native Postgres:

1. Start this compose file's `postgres` service (above).
2. Update `../backend/.env`'s `DATABASE_URL`:
   ```
   DATABASE_URL=postgresql+asyncpg://genai:<your-password>@127.0.0.1:5433/genai_dev
   ```
3. Run migrations directly — **skip** `setup.sh`'s Postgres role/database
   creation step, since the container's own `POSTGRES_USER`/
   `POSTGRES_PASSWORD`/`POSTGRES_DB` environment variables already created
   both:
   ```bash
   cd ../backend
   ./venv/bin/alembic upgrade head
   ```

For an individual **application** to use the dockerized Qdrant instead of
whatever Qdrant its `vector_backend` config currently points at, set its
`vector_backend_config` via the admin API:

```bash
curl -X PATCH http://localhost:8020/admin/api/v1/applications/<id> \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"vector_backend": "qdrant", "vector_backend_config": {"url": "http://127.0.0.1:6343"}}'
```

(This is the same `vector_backend_config` field documented in
[../docs/04-vector-store-adapters.md](../docs/04-vector-store-adapters.md)
— pointing it at a different URL is already a supported, ordinary
config change, not a special case for Docker.)
