"""Application factory and server entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from cache_test.api.api import router as api_router
from cache_test.api.payload import router as payload_router
from cache_test.config import Settings
from cache_test.db import create_db_engine, create_session_factory, init_db
from cache_test.transformer import SimulatedTransformer, Transformer
from cache_test.utils import envelope


def create_app(
    settings: Settings | None = None, transformer: Transformer | None = None
) -> FastAPI:
    """Build the application.

    Dependencies are injected here rather than imported as globals so tests
    can run against an isolated database.
    """
    settings = settings or Settings()
    engine = create_db_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(engine)
        yield
        engine.dispose()

    app = FastAPI(title="Caching service", lifespan=lifespan)
    app.state.session_factory = create_session_factory(engine)
    app.state.transformer = transformer or SimulatedTransformer(
        settings.transformer_delay_seconds
    )
    app.include_router(api_router)
    app.include_router(payload_router)
    envelope.install(app)

    return app


def run() -> None:
    uvicorn.run("cache_test.main:create_app", factory=True, host="0.0.0.0", port=8000)
