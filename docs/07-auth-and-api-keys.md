# Auth: two separate realms

This service has two completely independent authentication mechanisms,
serving different purposes, and they are never interchangeable.

## Application API keys (service-to-service)

Table `application_api_keys`: `key_prefix` (first 12 chars, indexed —
finds the candidate row cheaply before the expensive comparison),
`key_hash` (`sha256` of the full key), `last_four` (shown in the admin UI
so a key is identifiable without ever re-displaying the full value),
`label`, `is_active`, `revoked_at`, `last_used_at`.

Issuance (`POST /admin/api/v1/applications/{id}/api-keys`):

```python
secret_part = secrets.token_urlsafe(32)   # 256 bits of entropy
full_key = f"gak_{secret_part}"
# store only: key_prefix = full_key[:12], key_hash = sha256(full_key), last_four = full_key[-4:]
```

The full key is returned in the response body **exactly once**. After
that, only the hash exists — there is no "forgot my key, show it again"
path, by design (the same shape as GitHub personal access tokens or Stripe
API keys).

Verification (`get_current_application`, `app/core/deps.py`): the
`X-API-Key` header is looked up by prefix, then `sha256`-hashed and
compared with `secrets.compare_digest` against the stored hash of every
candidate with that prefix. A match resolves the owning `Application` row
(and rejects it if the application itself has been deactivated).

### Why `sha256`, not the Fernet encryption used elsewhere

Two different kinds of secret exist in this service, and they get two
different treatments — worth understanding the distinction, not just
copying the pattern:

- **API keys** (this table) only ever need "does this match what I
  issued" — verification, never retrieval. Hashing is strictly correct
  here: it needs no key management, and it structurally cannot suffer a
  "the encryption key was lost, now the data is unreadable" failure mode,
  because there's nothing to decrypt.
- **Provider/backend secrets** (`Application.embedding_api_key_encrypted`,
  `vector_backend_secret_encrypted`) must be **read back** — this service
  has to hand OpenAI or Qdrant the plaintext key on every call. These use
  `cryptography.fernet.Fernet`, keyed by this service's own
  `ENCRYPTION_KEY` (`app/core/crypto.py`).

And within the API-key case, plain `sha256` rather than `bcrypt` is
deliberate: bcrypt's engineered slowness exists to defend against
brute-forcing a *human-chosen, low-entropy* secret — a password someone
picked. These keys are `secrets.token_urlsafe(32)`-generated, 256 bits of
entropy each; guessing one is computationally hopeless regardless of hash
speed, so a fast hash is both sufficient and avoids adding deliberate CPU
cost to every single authenticated request this service ever serves.

## Admin login (human, independent realm)

Table `admin_users` — structurally unconnected to `applications` or
anything a consuming app has. Standard, well-established pattern:
`passlib` bcrypt for password hashing (bcrypt's slowness *is* warranted
here — this is exactly the human-chosen-secret case above), `python-jose`
JWT (HS256, this service's own `JWT_SECRET_KEY`, never shared with
anything else) for session tokens.

Two transports for the same JWT:

- **API clients**: `Authorization: Bearer <token>`
  (`get_current_admin`, `app/core/deps.py`).
- **The browser admin UI**: the same access token, stored in an HttpOnly
  cookie (`get_current_admin_ui`, `app/core/ui_auth.py`) — a browser
  navigating between pages doesn't naturally carry a custom header, so the
  UI needs cookie transport, but it's verifying the identical token format
  with the identical `decode_token()` function either way.

The login endpoint is rate-limited by client IP
(`enforce_login_rate_limit`) — the one place in this service where a
guessable, human-chosen secret is actually at risk; API keys don't need
this same protection since they're never guessable.

## What's deliberately not built

One flat admin role in V1 — `require_admin` means "any authenticated row
in `admin_users`," full stop. Multi-role RBAC is a real gap only once a
second human administrator needs permissions genuinely narrower than full
access; today there's one operator, and building role granularity against
a hypothetical second admin would be speculative.
