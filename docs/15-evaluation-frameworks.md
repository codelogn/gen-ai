# Evaluation frameworks

gen-ai has no way to answer "is retrieval actually any good" without this
feature — every earlier verification in this codebase's own history was
manual (hand-picked queries, eyeballing scores). This adds a built-in
evaluation feature: given test queries with known-good answers, run gen-ai's
actual configured retrieval against them and score the results using real,
independent, open-source evaluation frameworks.

## Why this looks different from `VectorStoreAdapter`/`RetrievalStrategy`

Read this before anything else in this doc. Those two interfaces are
**"pick one, it's how production behaves"** — an application has exactly
one active backend and one active strategy. Evaluation frameworks are
different: the whole point of supporting several is running them **all at
once against the same test cases** and comparing their opinions — a
fan-out, not a switch. There is deliberately no
`get_evaluation_framework(application)` single-choice factory; instead
`EvaluationService` (`app/modules/evaluation/service.py`) takes a **list**
of framework names per run and executes every one of them.

This was proven directly, not just designed this way for its own sake: the
same test case, run through Ragas and DeepEval simultaneously with the
*identical* judge model, produced **context precision scores of 0.0 and
1.0 respectively** — a real, meaningful disagreement between two
legitimate, independently-implemented metrics. A team relying on only one
framework would get a false sense of confidence in either direction. Seeing
both side by side is the actual value proposition here, not a nice-to-have.

## Which frameworks, and why these specifically

Researched directly before building this (see the design conversation for
the full comparison): **Ragas** and **DeepEval**, both Apache 2.0, both
actively maintained, both support custom/local judge LLMs. **TruLens**
(MIT) is legitimate open source but has slowed since its acquisition by
TruEra. **Arize Phoenix** — despite being the most popular by GitHub stars
— is licensed under Elastic License 2.0, which is **not** OSI-approved open
source (it restricts offering it as a hosted service to third parties), and
was excluded on that basis alone, not preference.

A third framework, **`native`**, needs no third-party library or judge LLM
at all — plain precision@k/recall@k/MRR computed by comparing retrieved
memory IDs against caller-supplied ground truth. It's the fast, free,
always-available baseline every run can include regardless of whether a
judge LLM is configured.

## A genuinely new capability: gen-ai's first chat-completion LLM

Every prior capability in this service only ever **embedded** text
(`EmbeddingProviderRegistry`, raw `httpx` calls). Ragas and DeepEval's
metrics work via **LLM-as-judge** — a chat-completion model scores things
like "is this context actually relevant to the query." That's a genuinely
different capability from embedding, not a variant of it.

`Application` gained four new fields mirroring `embedding_*` exactly:
`judge_llm_provider`, `judge_llm_model`, `judge_llm_base_url`,
`judge_llm_api_key_encrypted`. `build_judge_chat_model()`
(`app/modules/evaluation/judge_llm.py`) is the one place that branches on
provider to build a real LangChain `ChatOllama`/`ChatOpenAI` — the same
provider-branching shape as every other factory in this codebase, applied
to a capability that didn't exist here before.

**One judge LLM, two framework integrations**: `DeepEvalLangchainAdapter`
(same file) wraps that identical chat model so DeepEval's metrics use the
exact same judge Ragas does via `LangchainLLMWrapper` — one config, one
underlying call path, not two independent judge-LLM setups to keep in sync.

## Judge model capability matters — a real finding, not a caveat

Verified directly during development: a small local model
(`llama3.2:1b`) **failed outright** on DeepEval's metrics —
`"Evaluation LLM outputted an invalid JSON. Please use a better evaluation
model."` (DeepEval's own error message) — because DeepEval's metrics need
reliable structured JSON output, which a 1B-parameter model can't
consistently produce. The identical test against a larger model
(`llama3.2`, 3B) succeeded cleanly. Separately, the same 1B model produced
an internally-inconsistent Ragas score (`context_precision: 0.0` for a case
where the retrieval was obviously correct) and a genuine parser failure on
another metric.

**This is not a bug in the integration** — the underlying mechanism was
verified independently to work correctly (a controlled test with an
obviously-relevant context scored 0.9999, an obviously-irrelevant one
scored 0.0, with the identical code path). It's an honest, useful
operational finding: **if judge-LLM-based evaluation results look noisy or
contradictory, suspect the judge model's capability before suspecting a
bug.** A tiny local model is a fine default for the embedding provider (it
doesn't need to reason, just represent meaning as a vector) but is a poor
choice as an evaluation judge, which requires actual structured reasoning.

Even the larger model isn't perfectly reliable, either: a separate
three-framework run against the same `llama3.2` (3B) judge produced a real
`ragas` failure — `Invalid json output... OUTPUT_PARSING_FAILURE` — on a
prompt where `deepeval`, using the identical judge and the identical
retrieved context, succeeded and returned real scores in the same request.
Ragas's structured-output prompts are apparently less forgiving of a
non-frontier local model's occasional formatting slip than DeepEval's are.
This is exactly the scenario per-framework error isolation exists for
(see "Async by design" below and the try/except in every framework
implementation): the run still completed, `native` and `deepeval`'s real
results still rendered, and `ragas`'s cell showed the actual error instead
of taking down the whole report.

## Retrieval-only vs. answer-quality metrics

Every `EvaluationFramework.evaluate_case()` receives four optional pieces
of ground truth per test case, from least to most demanding:

| Field | Enables | Frameworks |
|---|---|---|
| `expected_memory_ids` | precision@k, recall@k, MRR | `native` |
| `expected_context` | context precision, context recall | `ragas`, `deepeval` |
| `generated_answer` | faithfulness, answer relevancy | `ragas`, `deepeval` |

gen-ai never generates answers itself — `generated_answer`, when supplied,
comes from whoever is calling this (e.g. the example chat client), the
same way document chunks come from the caller, not from gen-ai chunking
anything itself. A test case with none of these three fields gets
`{"skipped": "..."}` from every framework that needs at least one of them
— never a silent, misleading blank result.

## Async by design — this is gen-ai's first background job

Multiple frameworks × multiple cases × real judge-LLM calls is genuinely
slow (`LLMContextRecall` alone was observed taking tens of seconds against
a small local model). `POST /api/v1/evaluations` returns `202` with a
`pending` run immediately; a background task (`asyncio.create_task`, its
own fresh DB session — the same fire-and-forget-with-its-own-session shape
used elsewhere for anything that must outlive the triggering request) does
the actual work. The caller polls `GET .../evaluations/{run_id}` for the
completed report. No task queue at this scale — consistent with this
codebase's stated non-goal against one.

## Data model — one table, not three

`EvaluationRun` (`app/modules/evaluation/models.py`) holds the whole
report as one JSONB column, following the same pragmatic-schema instinct
already used for the generic `memories` table: evaluation runs are
diagnostic/on-demand, not high-throughput traffic, and there's no present
need for cross-run analytical SQL queries that would justify normalizing
cases/results into separate tables.

## Extensibility

See [16-adding-an-evaluation-framework.md](./16-adding-an-evaluation-framework.md)
for the recipe to add a fourth framework (e.g. TruLens later, if a concrete
reason to compare against it emerges).
