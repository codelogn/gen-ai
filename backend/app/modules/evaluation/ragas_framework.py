"""RagasEvaluationFramework.

Uses ragas's older `ragas.metrics`/`LangchainLLMWrapper` API rather than
the newer `ragas.metrics.collections`/`llm_factory` API — verified
directly (see docs/15-evaluation-frameworks.md) that the newer API expects
a raw provider client (openai.OpenAI, anthropic.Anthropic, ...) rather
than a LangChain chat model, which would mean Ragas and DeepEval can no
longer share one judge-LLM builder (judge_llm.py). The older API is
deprecated (removal targeted for ragas v1.0) but fully functional today
and accepts the same LangChain chat model DeepEval's adapter wraps —
revisit when the old API is actually removed, not before.
"""

from typing import Any, Optional
from uuid import UUID

from ragas.dataset_schema import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithoutReference,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
)

from app.modules.applications.models import Application
from app.modules.evaluation.base import EvaluationFramework
from app.modules.retrieval.base import SearchResult


class RagasEvaluationFramework(EvaluationFramework):
    name = "ragas"

    async def evaluate_case(
        self,
        application: Application,
        query: str,
        retrieved: list[SearchResult],
        expected_memory_ids: Optional[list[UUID]],
        expected_context: Optional[str],
        generated_answer: Optional[str],
        judge_llm: Optional[Any],
    ) -> dict:
        if not expected_context and not generated_answer:
            return {"skipped": "no expected_context or generated_answer provided"}
        if judge_llm is None:
            return {"error": "no judge LLM available for this run"}

        judge = LangchainLLMWrapper(judge_llm)
        contexts = [r.content for r in retrieved] or [""]
        scores: dict = {}

        try:
            if expected_context:
                sample = SingleTurnSample(
                    user_input=query, reference=expected_context, retrieved_contexts=contexts
                )
                scores["context_precision"] = await LLMContextPrecisionWithReference(
                    llm=judge
                ).single_turn_ascore(sample)
                scores["context_recall"] = await LLMContextRecall(llm=judge).single_turn_ascore(sample)

            if generated_answer:
                sample = SingleTurnSample(
                    user_input=query, response=generated_answer, retrieved_contexts=contexts
                )
                scores["faithfulness"] = await Faithfulness(llm=judge).single_turn_ascore(sample)
                # ResponseRelevancy needs its own embeddings model — reusing
                # the application's own embedding provider would need a
                # LangChain Embeddings wrapper too; deferred, not built in
                # this phase (see docs/15-evaluation-frameworks.md's non-goals).
                if not expected_context:
                    # No reference was available for context_precision above —
                    # LLMContextPrecisionWithoutReference substitutes the
                    # generated answer as its relevance proxy instead.
                    scores["context_precision"] = await LLMContextPrecisionWithoutReference(
                        llm=judge
                    ).single_turn_ascore(sample)
        except Exception as exc:
            return {"error": str(exc)[:1000], **{k: round(v, 4) for k, v in scores.items()}}

        return {k: round(v, 4) for k, v in scores.items()}


_ragas_framework = RagasEvaluationFramework()


def get_ragas_framework() -> RagasEvaluationFramework:
    return _ragas_framework
