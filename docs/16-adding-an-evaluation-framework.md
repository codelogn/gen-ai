# Recipe: adding a fourth evaluation framework

Say a concrete reason comes up to compare against, e.g., TruLens. Steps.

Read [15-evaluation-frameworks.md](./15-evaluation-frameworks.md) first if
you haven't — in particular the "why this looks different from
`VectorStoreAdapter`/`RetrievalStrategy`" section. `FRAMEWORK_REGISTRY` in
`EvaluationService` is a **fan-out map**, not a single-choice factory like
`vectorstore/factory.py` or `retrieval/factory.py`. Adding a framework here
means it becomes a fourth thing every run *can* request alongside the
others, not a fourth option that replaces one of the existing three.

## 1. Implement `EvaluationFramework`

New file `app/modules/evaluation/your_framework.py`:

```python
from app.modules.evaluation.base import EvaluationFramework

class YourFramework(EvaluationFramework):
    name = "your_framework"

    async def evaluate_case(self, application, query, retrieved, expected_memory_ids,
                             expected_context, generated_answer, judge_llm) -> dict:
        # judge_llm is a LangChain BaseChatModel (ChatOllama/ChatOpenAI),
        # already built once per run by EvaluationService — do not build
        # your own here. If your library needs a different wrapper shape
        # than LangchainLLMWrapper (ragas) or DeepEvalBaseLLM (deepeval),
        # write a third thin adapter in judge_llm.py, but keep the
        # underlying chat model itself shared across all frameworks —
        # that's the point of building it once per run.
        if judge_llm is None:
            return {"error": "no judge LLM available for this run"}
        if not expected_context and not generated_answer:
            return {"skipped": "no expected_context or generated_answer provided"}

        # ... call your library's actual metric functions here, against
        # `retrieved` (the REAL results from the application's configured
        # RetrievalStrategy — never a special eval-only query path) ...
        return {"your_metric": 0.83}

_your_framework = YourFramework()

def get_your_framework() -> YourFramework:
    return _your_framework
```

Two rules from the existing three implementations worth keeping:
- **Never crash the whole run for one framework's failure.** Wrap the
  actual metric calls in `try/except` and return
  `{"error": str(exc)[:1000], **whatever_partial_scores_you_got}` — see
  `ragas_framework.py`/`deepeval_framework.py` for the pattern. A report
  where one framework failed on one case is still useful for the other
  frameworks/cases; a crashed background task loses the whole run.
- **Return `{"skipped": "<reason>"}`, never a silently-omitted key**, when
  the case doesn't have what your framework needs. A missing key in the
  report reads as a bug; an explicit `skipped` reads as expected behavior.

## 2. Register in `FRAMEWORK_REGISTRY`

`app/modules/evaluation/service.py`:

```python
from app.modules.evaluation.your_framework import get_your_framework

FRAMEWORK_REGISTRY = {
    "native": get_native_framework,
    "ragas": get_ragas_framework,
    "deepeval": get_deepeval_framework,
    "your_framework": get_your_framework,  # add this
}
```

That's the entire wiring step — `EvaluationService.run()` already validates
requested framework names against this dict's keys and rejects unknown
ones with a clear `ValueError`, and `_build_report()` already loops
`for framework_name in frameworks: ...` generically, so nothing else in
the service needs to change.

## 3. New dependency? Check the LangChain-core version pin carefully

If your framework, like Ragas and DeepEval, is LLM-as-judge-based and
built on LangChain, check what `langchain-core` range it needs against
what's already pinned in `requirements.txt` before assuming a plain `pip
install` will work cleanly. This build hit a real, non-obvious conflict
here: `langchain-community==0.4.2` silently removed the
`chat_models.vertexai` submodule that Ragas's own import chain depends on
unconditionally (not something ragas itself did — a side effect of
`langchain-community`'s own version bump), forcing a pin to `0.4.1`
specifically. Don't assume the newest patch version of a transitive
dependency is safe — verify a fresh install actually still imports
correctly, not just that `pip` resolved without error.

## 4. Admin UI checkbox

`app/admin_ui/templates/application_evaluations.html` has one `<input
type="checkbox" name="frameworks" value="...">` per framework in the "Run
a new evaluation" form. Add a matching one for `your_framework` — no other
template change needed, since `evaluation_run_detail.html`'s report view
already iterates `case.results.items()` generically per framework rather
than hard-coding column names.

## 5. Verify

The acceptance bar used for both Ragas and DeepEval, applied here: run the
same test case, with the same judge LLM, through your new framework
**and** at least one existing one, and confirm the scores are in the same
ballpark and point the same direction — a case with obviously-correct
retrieval should score high on both, one with obviously-wrong retrieval
should score low on both. They should not be *identical* (each framework
has its own metric implementation) but a wild disagreement (one says 0.95,
the other says 0.05, on the same unambiguous case) means something is
wired wrong in your adapter — most likely the judge LLM isn't actually
being invoked, or your prompt/parsing is broken — not a legitimate
framework difference. Real, legitimate disagreement does happen (see the
Ragas-vs-DeepEval `context_precision` example in
[15-evaluation-frameworks.md](./15-evaluation-frameworks.md)) but only on
genuinely ambiguous cases, not clear-cut ones.

Also re-run the small-vs-large judge model comparison from
[15-evaluation-frameworks.md](./15-evaluation-frameworks.md) against your
new framework specifically — if it needs structured output from the judge
(most LLM-as-judge libraries do), confirm what happens with a small local
model: a clear error is fine, a silent wrong answer is not.
