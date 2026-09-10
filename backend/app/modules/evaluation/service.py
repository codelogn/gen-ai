"""EvaluationService — the fan-out orchestrator.

Async because multiple frameworks x multiple cases x real judge-LLM calls
is genuinely slow — POST /api/v1/evaluations returns immediately with a
"pending" run; a background task (its own fresh DB session, same
fire-and-forget-with-its-own-session shape used elsewhere for anything
that must outlive the triggering request) does the actual work and the
caller polls GET .../evaluations/{run_id} for the completed report. This
is gen-ai's first background-job pattern; no task queue needed at this
scale — see docs/15-evaluation-frameworks.md and docs/10-latest-practices-checklist.md.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.applications.models import Application
from app.modules.evaluation.deepeval_framework import get_deepeval_framework
from app.modules.evaluation.judge_llm import JudgeLLMNotConfigured, build_judge_chat_model
from app.modules.evaluation.models import EvaluationRun
from app.modules.evaluation.native_framework import get_native_framework
from app.modules.evaluation.ragas_framework import get_ragas_framework
from app.modules.retrieval.factory import get_strategy

logger = logging.getLogger("gen_ai.evaluation")

# Frameworks that need a judge LLM — used to decide whether to build one
# once per run (expensive-ish, so built at most once, not once per case).
JUDGE_LLM_FRAMEWORKS = {"ragas", "deepeval"}

FRAMEWORK_REGISTRY = {
    "native": get_native_framework,
    "ragas": get_ragas_framework,
    "deepeval": get_deepeval_framework,
}


class EvaluationService:
    async def run(
        self,
        db: AsyncSession,
        application: Application,
        frameworks: list[str],
        cases: list[dict],
    ) -> EvaluationRun:
        unknown = [f for f in frameworks if f not in FRAMEWORK_REGISTRY]
        if unknown:
            raise ValueError(f"Unknown evaluation framework(s): {unknown}")

        run = EvaluationRun(
            application_id=application.id,
            frameworks=frameworks,
            input_cases=cases,
            status="pending",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        # Capture the primitive ID, not the ORM object — `application` came
        # from the request's own DB session, which closes once this
        # request returns. The background task re-fetches its own copy in
        # its own session (see _execute_background) to avoid a detached-
        # instance error, the same reason RequestLoggingMiddleware stashes
        # primitives on request.state rather than the Application object itself.
        asyncio.create_task(self._execute_background(run.id, application.id, frameworks, cases))

        return run

    async def _execute_background(
        self, run_id: uuid.UUID, application_id: uuid.UUID, frameworks: list[str], cases: list[dict]
    ) -> None:
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            run = await self.get_run(db, application_id, run_id)
            if run is None:
                logger.error(f"Evaluation run {run_id} vanished before background execution started")
                return

            app_result = await db.execute(select(Application).where(Application.id == application_id))
            application = app_result.scalar_one_or_none()
            if application is None:
                run.status = "failed"
                run.error = "Application was deleted before this evaluation could run"
                await db.commit()
                return

            run.status = "running"
            await db.commit()

            try:
                report = await self._build_report(db, application, frameworks, cases)
                run.report = report
                run.status = "completed"
            except Exception as exc:
                logger.exception(f"Evaluation run {run_id} failed")
                run.status = "failed"
                run.error = str(exc)[:2000]
            finally:
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()

    async def _build_report(
        self,
        db: AsyncSession,
        application: Application,
        frameworks: list[str],
        cases: list[dict],
    ) -> dict:
        # Built once per run, not once per case/framework — construction is
        # cheap but each judge-LLM-backed metric call already costs a real
        # network round trip, no reason to also rebuild the client object
        # repeatedly. None of the requested frameworks needing one means we
        # skip this step and every judge-LLM-based framework's evaluate_case
        # gets judge_llm=None, which they turn into a clear per-case
        # "no judge LLM available" error rather than crashing.
        judge_llm = None
        judge_llm_error: Optional[str] = None
        if JUDGE_LLM_FRAMEWORKS & set(frameworks):
            try:
                judge_llm = build_judge_chat_model(application)
            except JudgeLLMNotConfigured as exc:
                judge_llm_error = str(exc)
                logger.warning(f"Judge LLM not configured for application {application.slug}: {exc}")

        report_cases = []
        for case in cases:
            query = case["query"]
            namespace = case["namespace"]
            subject_id = case.get("subject_id")
            # .get(..., []) alone isn't enough: Pydantic's model_dump(mode="json")
            # serializes an unset Optional[list] field as an explicit JSON
            # null, so the key IS present with value None — "or []" catches
            # that case too, not just a genuinely-missing key.
            expected_memory_ids = [uuid.UUID(i) for i in (case.get("expected_memory_ids") or [])] or None
            expected_context = case.get("expected_context")
            generated_answer = case.get("generated_answer")

            strategy = get_strategy(application)
            retrieved = await strategy.search(
                db, application, query=query, top_k=case.get("top_k", 5),
                namespace=namespace, subject_id=subject_id,
            )

            results = {}
            for framework_name in frameworks:
                if framework_name in JUDGE_LLM_FRAMEWORKS and judge_llm_error:
                    results[framework_name] = {"error": judge_llm_error}
                    continue
                framework = FRAMEWORK_REGISTRY[framework_name]()
                results[framework_name] = await framework.evaluate_case(
                    application, query, retrieved, expected_memory_ids,
                    expected_context, generated_answer, judge_llm,
                )

            report_cases.append({
                "query": query,
                "retrieved": [
                    {"id": str(r.memory_id), "content": r.content, "score": r.score} for r in retrieved
                ],
                "results": results,
            })

        return {"cases": report_cases}

    async def get_run(self, db: AsyncSession, application_id: uuid.UUID, run_id: uuid.UUID) -> Optional[EvaluationRun]:
        result = await db.execute(
            select(EvaluationRun).where(
                EvaluationRun.id == run_id, EvaluationRun.application_id == application_id
            )
        )
        return result.scalar_one_or_none()

    async def list_runs(self, db: AsyncSession, application_id: uuid.UUID, limit: int = 50) -> list[EvaluationRun]:
        result = await db.execute(
            select(EvaluationRun)
            .where(EvaluationRun.application_id == application_id)
            .order_by(EvaluationRun.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


evaluation_service = EvaluationService()
