"""DeepEvalEvaluationFramework.

Uses the same underlying judge chat model as RagasEvaluationFramework,
wrapped via DeepEvalLangchainAdapter (app/modules/evaluation/judge_llm.py)
— one judge-LLM config, two independent framework integrations. Verified
directly during development that DeepEval's metrics need a judge capable
of reliable structured JSON output: a small local model (llama3.2:1b)
failed outright ("Evaluation LLM outputted an invalid JSON. Please use a
better evaluation model." — DeepEval's own error message), while a larger
one (llama3.2, 3B) succeeded cleanly. This is a genuine judge-model-
capability finding, not an integration bug — see
docs/15-evaluation-frameworks.md.
"""

from typing import Any, Optional
from uuid import UUID

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase

from app.modules.applications.models import Application
from app.modules.evaluation.base import EvaluationFramework
from app.modules.evaluation.judge_llm import DeepEvalLangchainAdapter
from app.modules.retrieval.base import SearchResult


class DeepEvalEvaluationFramework(EvaluationFramework):
    name = "deepeval"

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

        adapter = DeepEvalLangchainAdapter(judge_llm, judge_llm.model if hasattr(judge_llm, "model") else "judge")
        contexts = [r.content for r in retrieved] or [""]
        scores: dict = {}

        try:
            if expected_context:
                tc = LLMTestCase(
                    input=query,
                    actual_output=generated_answer or "",
                    expected_output=expected_context,
                    retrieval_context=contexts,
                )
                scores["contextual_precision"] = round(
                    await ContextualPrecisionMetric(model=adapter, include_reason=False).a_measure(tc), 4
                )
                scores["contextual_recall"] = round(
                    await ContextualRecallMetric(model=adapter, include_reason=False).a_measure(tc), 4
                )

            if generated_answer:
                tc = LLMTestCase(
                    input=query, actual_output=generated_answer, retrieval_context=contexts
                )
                scores["faithfulness"] = round(
                    await FaithfulnessMetric(model=adapter, include_reason=False).a_measure(tc), 4
                )
                scores["answer_relevancy"] = round(
                    await AnswerRelevancyMetric(model=adapter, include_reason=False).a_measure(tc), 4
                )
        except Exception as exc:
            return {"error": str(exc)[:1000], **scores}

        return scores


_deepeval_framework = DeepEvalEvaluationFramework()


def get_deepeval_framework() -> DeepEvalEvaluationFramework:
    return _deepeval_framework
