import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_secret
from app.modules.applications.models import Application
from app.modules.applications.schemas import ApplicationCreate, ApplicationUpdate


class ApplicationService:
    async def list_applications(self, db: AsyncSession) -> list[Application]:
        result = await db.execute(select(Application).order_by(Application.created_at.desc()))
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, application_id: uuid.UUID) -> Optional[Application]:
        result = await db.execute(select(Application).where(Application.id == application_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, db: AsyncSession, slug: str) -> Optional[Application]:
        result = await db.execute(select(Application).where(Application.slug == slug))
        return result.scalar_one_or_none()

    async def create(
        self, db: AsyncSession, data: ApplicationCreate, created_by_admin_id: uuid.UUID
    ) -> Application:
        existing = await self.get_by_slug(db, data.slug)
        if existing is not None:
            raise ValueError(f"An application with slug '{data.slug}' already exists")

        app_row = Application(
            slug=data.slug,
            display_name=data.display_name,
            vector_backend=data.vector_backend,
            vector_backend_config=data.vector_backend_config,
            vector_backend_secret_encrypted=(
                encrypt_secret(data.vector_backend_secret) if data.vector_backend_secret else None
            ),
            retrieval_strategy=data.retrieval_strategy,
            retrieval_strategy_config=data.retrieval_strategy_config,
            embedding_provider=data.embedding_provider,
            embedding_model=data.embedding_model,
            embedding_base_url=data.embedding_base_url,
            embedding_api_key_encrypted=(
                encrypt_secret(data.embedding_api_key) if data.embedding_api_key else None
            ),
            judge_llm_provider=data.judge_llm_provider,
            judge_llm_model=data.judge_llm_model,
            judge_llm_base_url=data.judge_llm_base_url,
            judge_llm_api_key_encrypted=(
                encrypt_secret(data.judge_llm_api_key) if data.judge_llm_api_key else None
            ),
            rate_limit_per_minute=data.rate_limit_per_minute,
            created_by_admin_id=created_by_admin_id,
        )
        db.add(app_row)
        await db.commit()
        await db.refresh(app_row)
        return app_row

    def _is_backend_changing(self, app_row: Application, data: ApplicationUpdate) -> bool:
        backend_changed = (
            data.vector_backend is not None and data.vector_backend != app_row.vector_backend
        )
        # Changing the embedding model can change dimension, which also
        # invalidates the existing vector store the same way a backend
        # switch does — see docs/04-vector-store-adapters.md.
        model_changed = (
            data.embedding_model is not None and data.embedding_model != app_row.embedding_model
        )
        provider_changed = (
            data.embedding_provider is not None
            and data.embedding_provider != app_row.embedding_provider
        )
        return backend_changed or model_changed or provider_changed

    async def update(
        self, db: AsyncSession, application_id: uuid.UUID, data: ApplicationUpdate
    ) -> tuple[Optional[Application], Optional[str]]:
        """Returns (updated_application, warning_message_or_None)."""
        app_row = await self.get(db, application_id)
        if app_row is None:
            return None, None

        warning = None
        if self._is_backend_changing(app_row, data):
            app_row.vector_backend_generation += 1
            # Reset dimension so the next write re-detects it and
            # re-provisions the new generation's store — MemoryService's
            # _ensure_provisioned() gates provisioning on this being unset.
            # Without this reset, a backend switch would bump the
            # generation number but the new store would never actually get
            # created, since dimension (from the OLD backend) would still
            # look "already known."
            app_row.embedding_dimension = None
            warning = (
                f"vector_backend/embedding settings changed — a fresh, empty store "
                f"will be provisioned under generation {app_row.vector_backend_generation} "
                f"on the next write. Existing data has NOT been deleted, but search "
                f"results will be empty until data is re-upserted. See "
                f"docs/04-vector-store-adapters.md."
            )

        update_data = data.model_dump(exclude_unset=True)
        secret_fields = {"vector_backend_secret": "vector_backend_secret_encrypted",
                          "embedding_api_key": "embedding_api_key_encrypted",
                          "judge_llm_api_key": "judge_llm_api_key_encrypted"}
        for plaintext_field, encrypted_field in secret_fields.items():
            if plaintext_field in update_data:
                plaintext = update_data.pop(plaintext_field)
                setattr(app_row, encrypted_field, encrypt_secret(plaintext) if plaintext else None)

        for field, value in update_data.items():
            setattr(app_row, field, value)

        await db.commit()
        await db.refresh(app_row)
        return app_row, warning

    async def deactivate(self, db: AsyncSession, application_id: uuid.UUID) -> bool:
        """Soft-disable only — never a hard delete, per design."""
        app_row = await self.get(db, application_id)
        if app_row is None:
            return False
        app_row.is_active = False
        await db.commit()
        return True


application_service = ApplicationService()
