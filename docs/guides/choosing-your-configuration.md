# Choosing your configuration: a quick decision guide

Three dropdowns, three checkboxes — this page is a fast, scannable
reference for picking them, for whoever's about to click through the
admin panel. It intentionally repeats nothing about *why* each option
works the way it does; for that, see the narrative docs linked from each
section. Start here if you just need to decide; go there if you want to
understand.

## Vector backend

*Where do the vectors physically live?* (dropdown values:
`sqlite_vec`, `pgvector`, `qdrant`)

| Pick... | If... |
|---|---|
| **`sqlite_vec`** | You're getting started, testing, or expect low traffic. No extra infrastructure to run — a local file. |
| **`pgvector`** | You already run Postgres for this service's control plane and want everything in one place, at moderate traffic. |
| **`qdrant`** | You expect heavy search traffic or large data volumes, and are willing to run a dedicated server for it. |

Full reasoning: [04-vector-store-adapters.md](../04-vector-store-adapters.md).
Changing this later starts your data over from scratch (see
[guides/admin-panel-guide.md](./admin-panel-guide.md)) — pick with your
expected scale in mind, but don't agonize; it's not a one-way door, just
a re-indexing cost.

## Retrieval strategy

*How does a query become ranked results?* (dropdown values: `native`,
`langchain`, `reranked`)

```
Does your data have a lot of proper nouns, product codes,
or jargon that pure "meaning" search might misrank?
  │
  ├─ Yes ──► langchain (hybrid keyword + vector search)
  │
  └─ No, or not sure yet
       │
       Is result QUALITY worth extra CPU cost per search,
       and are you not already using langchain for the above?
         │
         ├─ Yes ──► reranked (cross-encoder)
         │
         └─ No / just get started ──► native (the default)
```

| Pick... | If... |
|---|---|
| **`native`** | The sensible default — plain "find the closest match by meaning." Start here. |
| **`langchain`** | Your data has specific names/codes/jargon a pure meaning-search sometimes misranks (see the "Mercurial vs. Mercury" example in [05](../05-retrieval-strategies.md)). |
| **`reranked`** | You want the most accurate ranking available and can afford extra CPU per search — it re-scores results with a cross-encoder model. **Not a universal upgrade**: verified to fix some misranking cases and *not* others (see [05](../05-retrieval-strategies.md#why-reranking-demonstrated-not-just-asserted)) — measure it on your own data with the evaluation feature before assuming it helps. |

`langchain` and `reranked` address the *same class* of problem (pure
vector search getting fooled) via different mechanisms — you generally
wouldn't turn both on for the same application. Full reasoning:
[05-retrieval-strategies.md](../05-retrieval-strategies.md).

## Embedding provider

*What turns text into something searchable?* (dropdown values: `ollama`,
`openai`)

| Pick... | If... |
|---|---|
| **`ollama`** | Free, runs locally, no API key, no data leaves your infrastructure. The default unless you have a reason not to. |
| **`openai`** | You need a specific OpenAI embedding model, are fine sending data to OpenAI's servers, and don't mind the per-use cost. |

Full reasoning: [06-embedding-providers.md](../06-embedding-providers.md).

## Evaluation frameworks

*Which framework(s) should I run to check retrieval quality?*
(checkboxes: `native`, `ragas`, `deepeval` — not mutually exclusive, run
more than one)

```
Do you already know exactly which memory ID(s) SHOULD come back
for your test queries?
  │
  ├─ Yes ──► check native (free, instant, no judge LLM needed)
  │
  └─ No / it's more subjective than an exact ID match
       │
       Is a judge LLM configured on this application?
         │
         ├─ No ──► configure one first (see admin-panel-guide.md),
         │         or stick to native for now
         │
         └─ Yes ──► check ragas AND deepeval together
                     (they sometimes disagree — see 15 — running
                     both, not just one, is the actual point)
```

| Check... | If... |
|---|---|
| **`native`** | Always — it's free and needs no judge LLM. Requires `expected_memory_ids` on your test cases. |
| **`ragas`** | You have a judge LLM configured and want context precision/recall/faithfulness scoring. |
| **`deepeval`** | Same as `ragas` — check both together, not one or the other, so you can compare. |

Full reasoning, including a real documented case where `ragas` and
`deepeval` disagreed on the same test case:
[15-evaluation-frameworks.md](../15-evaluation-frameworks.md).

## Still not sure?

Every one of these is changeable later without losing data — see
[guides/admin-panel-guide.md](./admin-panel-guide.md#editing-settings-later)
for what happens when you switch. Start with the defaults
(`sqlite_vec` / `native` / `ollama`, no judge LLM configured), get real
data flowing, and use the evaluation feature to measure whether a change
actually helps *your* data before committing to it.
