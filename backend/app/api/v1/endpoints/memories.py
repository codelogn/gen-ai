import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.idempotency import get_cached_response, idempotency_key_header, store_response
from app.core.rate_limit import enforce_rate_limit
from app.modules.applications.models import Application
from app.modules.memory.schemas import (
    BatchCreateResponse,
    MemoryBatchCreate,
    MemoryCreate,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySupersede,
    SearchResultResponse,
)
from app.modules.memory.service import memory_service
from app.modules.retrieval.factory import get_strategy

router = APIRouter(prefix="/memories", tags=["memories"])


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: MemoryCreate,
    response: Response,
    application: Application = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Depends(idempotency_key_header),
):
    cached = await get_cached_response(db, application, idempotency_key)
    if cached is not None:
        status_code, body = cached
        response.status_code = status_code
        return body

    memory = await memory_service.create(
        db,
        application,
        namespace=data.namespace,
        content=data.content,
        subject_id=data.subject_id,
        metadata=data.metadata,
        source_ref=data.source_ref,
    )
    result = MemoryResponse.model_validate(memory)
    await store_response(
        db, application, idempotency_key, status.HTTP_201_CREATED, result.model_dump(mode="json")
    )
    return result


@router.post("/batch", response_model=BatchCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_memories_batch(
    data: MemoryBatchCreate,
    response: Response,
    application: Application = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Depends(idempotency_key_header),
):
    cached = await get_cached_response(db, application, idempotency_key)
    if cached is not None:
        status_code, body = cached
        response.status_code = status_code
        return body

    created: list[uuid.UUID] = []
    failed: list[dict] = []
    for index, item in enumerate(data.items):
        try:
            memory = await memory_service.create(
                db,
                application,
                namespace=item.namespace,
                content=item.content,
                subject_id=item.subject_id,
                metadata=item.metadata,
                source_ref=item.source_ref,
            )
            created.append(memory.id)
        except Exception as exc:  # noqa: BLE001 — one bad item shouldn't fail the whole batch
            failed.append({"index": index, "error": str(exc)})

    result = BatchCreateResponse(created=created, failed=failed)
    await store_response(
        db, application, idempotency_key, status.HTTP_201_CREATED, result.model_dump(mode="json")
    )
    return result


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    data: MemorySearchRequest,
    application: Application = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    strategy = get_strategy(application)
    results = await strategy.search(
        db,
        application,
        query=data.query,
        top_k=data.top_k,
        namespace=data.namespace,
        subject_id=data.subject_id,
    )
    if data.min_score is not None:
        results = [r for r in results if r.score >= data.min_score]
    return MemorySearchResponse(
        results=[
            SearchResultResponse(
                id=r.memory_id, content=r.content, metadata=r.metadata, score=r.score,
                created_at=r.created_at,
            )
            for r in results
        ]
    )


@router.post("/{memory_id}/supersede", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def supersede_memory(
    memory_id: uuid.UUID,
    data: MemorySupersede,
    response: Response,
    application: Application = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Depends(idempotency_key_header),
):
    cached = await get_cached_response(db, application, idempotency_key)
    if cached is not None:
        status_code, body = cached
        response.status_code = status_code
        return body

    new_memory = await memory_service.supersede(
        db, application, memory_id, content=data.content, metadata=data.metadata
    )
    if new_memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

    result = MemoryResponse.model_validate(new_memory)
    await store_response(
        db, application, idempotency_key, status.HTTP_201_CREATED, result.model_dump(mode="json")
    )
    return result


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    hard: bool = Query(default=False),
    application: Application = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    found = await memory_service.delete(db, application, memory_id, hard=hard)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: uuid.UUID,
    application: Application = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    memory = await memory_service.get(db, application.id, memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return memory


namespaces_router = APIRouter(tags=["memories"])


@namespaces_router.get("/namespaces")
async def list_namespaces(
    application: Application = Depends(enforce_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    return {"namespaces": await memory_service.list_namespaces(db, application.id)}
