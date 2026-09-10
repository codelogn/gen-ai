# Using the admin panel

This is a step-by-step guide to the admin panel at `/admin/ui/` — written
for whoever operates gen-ai day to day, not necessarily someone reading its
source code. If you want to understand *why* it's built this way instead
of *how to click through it*, see
[../02-multi-tenancy-and-adapters.md](../02-multi-tenancy-and-adapters.md)
and [../08-api-reference.md](../08-api-reference.md) — everything the panel
does, it does by calling the same REST endpoints documented there.

## Logging in

Go to `http://<your-host>:8020/admin/ui/login` (locally:
`http://localhost:8020/admin/ui/login`). Enter the admin email and
password you were given (or that you seeded when this service was set up
— see the main README's seeding step if you need to create the first
admin account).

If you visit any admin page without being logged in, you'll be redirected
back here automatically — that's expected, not an error.

**Note**: your login session lasts 30 minutes. If the panel suddenly
starts rejecting your actions, you've likely just been logged out — log in
again.

## The applications list

After logging in you land on `/admin/ui/applications` — a table of every
application registered with this service so far. Each row shows its slug
(a short internal name), display name, which vector storage backend and
retrieval strategy it's using, its embedding provider, and whether it's
active.

Click **+ New application** to register a new one, or click any row's slug
to open its detail page.

## Registering a new application

An "application" here means any external system that will call this
service's API — a chatbot, a support tool, anything that wants AI-powered
memory or search. You'll fill in:

- **Slug**: a short, lowercase, URL-safe name (letters, numbers, hyphens)
  — pick something identifying, like `support-bot` or `docs-search`. This
  can't be changed later, so choose something you'll recognize in six
  months.
- **Display name**: a human-readable label — shown throughout the panel.
- **Vector backend** (a dropdown — this is *where the data physically
  lives*):
  - **`sqlite_vec`** — the simplest option. No extra setup, works
    instantly. Good for getting started or for low-traffic use.
  - **`pgvector`** — stores data in this service's own database. A good
    middle ground if you expect moderate traffic.
  - **`qdrant`** — a dedicated, purpose-built search engine. Choose this
    if you expect heavy search traffic or large amounts of data.

  Don't worry too much about getting this right the first time — you can
  change it later (see "Changing an application's settings" below), you
  just have to re-add your data afterward.

- **Retrieval strategy** (a dropdown — this is *how search results are
  ranked*):
  - **`native`** — plain "find the closest match by meaning." The
    sensible default.
  - **`langchain`** — combines meaning-based search with old-fashioned
    exact keyword matching. Better at catching specific names, codes, or
    unusual terms that a pure meaning-based search sometimes misranks
    (see [../00-rag-concepts-primer.md](../00-rag-concepts-primer.md) if
    you want to understand why this happens). If your data includes a lot
    of proper nouns, product names, or technical jargon, this is worth
    turning on.

  If you pick `langchain`, a second field appears — **hybrid keyword
  weight** — a number between 0 and 1 controlling how much the exact
  keyword match matters versus the meaning-based match. The default (0.3)
  means "mostly meaning-based, with some keyword boosting." Higher values
  lean more on exact wording.

- **Embedding provider** (a dropdown — this is *what turns text into
  something searchable*):
  - **`ollama`** — free, runs locally, no API key needed. The default and
    recommended choice unless you have a specific reason to use OpenAI.
  - **`openai`** — requires an API key (a field appears when you select
    this), sends your data to OpenAI's servers, costs money per use.

- **Embedding model**: the specific model name — for Ollama, something
  like `nomic-embed-text` (make sure it's been downloaded on the server
  first); for OpenAI, something like `text-embedding-3-small`.

- **Evaluation judge LLM** (optional — a dropdown, left as "(not
  configured)" by default): only needed if you plan to score retrieval
  quality using the **ragas** or **deepeval** evaluation frameworks (see
  "Evaluations" below). Same two provider choices as the embedding
  provider above (`ollama` or `openai`), but this one needs a
  **chat-capable** model, not an embedding model — for Ollama, something
  like `llama3.2`, not `nomic-embed-text`. You can skip this entirely and
  still use the **native** evaluation framework, which needs no LLM at
  all.

  **Worth knowing before you pick a model**: a small model (e.g. a 1B
  local model) is often fine as an embedding model but can be a poor judge
  — it may fail outright on `deepeval`'s metrics or give inconsistent
  `ragas` scores, because judging requires more structured reasoning than
  embedding does. If judge-based evaluation scores look noisy or
  contradictory, try a larger chat model here before assuming something's
  broken — see
  [../15-evaluation-frameworks.md](../15-evaluation-frameworks.md) for a
  worked example of exactly this.

Click **Create application**. You'll land on its detail page.

## The application detail page

Shows the configuration you just picked, plus two more sections:

### API keys

This is how the application you just registered will actually
authenticate to gen-ai. Type a label (e.g. "production" or "my laptop")
and click **Issue new key**.

**Important**: the full key is shown exactly once, right after you create
it, in a highlighted box. Copy it immediately — there is no way to see it
again afterward (this is intentional, for security — see
[../07-auth-and-api-keys.md](../07-auth-and-api-keys.md) if you're curious
why). If you lose it, revoke it and issue a new one.

Each key in the table shows only its first and last few characters, so you
can tell keys apart without ever seeing the full value again. Click
**Revoke** to immediately disable a key — this cannot be undone, and the
application using that key will start getting rejected immediately.

### Editing settings later

Click **Edit** to change any of the dropdowns or the display name.

**One thing worth understanding before you change the vector backend or
embedding model**: doing so starts your application's data over from
scratch. Your existing data isn't deleted, but search stops finding it
until you send it again. The edit screen will warn you about this before
you confirm — take it seriously if the application already has real data
in it.

## Logs & usage

Click **Logs & usage** from an application's detail page to see:

- **Usage summary**: total requests, error rate, and average/typical
  response time over the last 24 hours.
- **Recent requests**: a table of the most recent calls this application
  made — what endpoint, what it returned, how long it took, and which
  backend/strategy actually handled it.

This is the first place to look if an application reports something isn't
working — see
[../09-observability-and-troubleshooting.md](../09-observability-and-troubleshooting.md)
for a worked example of diagnosing a specific problem this way.

## Evaluations

Click **Evaluations** from an application's detail page to check whether
its retrieval is actually finding the right things — not just whether it's
*working* (that's what Logs & usage tells you) but whether it's *good*.
See [../00-rag-concepts-primer.md](../00-rag-concepts-primer.md) if you
want the underlying concepts explained first, and
[../15-evaluation-frameworks.md](../15-evaluation-frameworks.md) for the
full design reasoning behind everything below.

### Running an evaluation

1. **Pick which frameworks to run.** You can check more than one — they
   run side by side against the same test cases, so you can compare their
   opinions rather than trusting just one:
   - **native** — free, instant, no judge LLM needed. Give it
     `expected_memory_ids` (the IDs of the memories a good search *should*
     return) and it computes precision/recall/how-high-they-ranked
     directly, no AI judgment involved.
   - **ragas** / **deepeval** — need the judge LLM configured on this
     application (see "Registering a new application" above). Give them
     `expected_context` and/or `generated_answer` and they use the judge
     LLM to score things a strict ID match can't, like "does the retrieved
     text actually support this answer."

   If no judge LLM is configured, you'll see a warning banner — `native`
   still works fine without one.

2. **Paste your test cases** as a JSON array in the text box. Each case
   needs at least a `query` and a `namespace` (which namespace to search
   within — same as any real search request this application would make).
   Add whichever of `expected_memory_ids`, `expected_context`, or
   `generated_answer` your chosen frameworks need — leave the others as
   empty strings/arrays, or remove them.

3. Click **Run evaluation**. You'll be taken straight to the run's report
   page, which will say **pending** or **running** at first — judge-LLM-based
   frameworks can take anywhere from a few seconds to over a minute per
   case, especially against a small local model. Refresh the page to check
   again; there's no need to keep the tab open and waiting.

### Reading the report

Once **completed**, each test case shows two tables: what was actually
retrieved (the content and its similarity score), and the results from
each framework you ran. A framework's cell shows either its metric scores,
**skipped** (meaning that case didn't include what that framework needed
— not an error, just nothing to score), or **error** (something actually
went wrong — a missing judge LLM, or a framework-specific failure; the
message tells you which).

It's normal, and expected, for `ragas` and `deepeval` to disagree slightly
on the same case — they're independent implementations of similar ideas,
not two views of the same calculation. A large, obvious disagreement on a
clear-cut case (one says the retrieval was great, the other says it was
terrible, and to a human reading the retrieved text it's obviously one or
the other) is more often a sign the judge model is too small to reason
reliably than a bug — see the note about judge model size above.

## Deactivating an application

There's currently no "delete" button in the panel — applications are only
ever soft-disabled (via the API's `DELETE` endpoint), never permanently
removed, so historical data and logs are never lost by accident. If you
need to fully retire an application, ask whoever manages the underlying
database directly.
