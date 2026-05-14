from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings

_checkpointer: AsyncPostgresSaver | None = None
_checkpointer_ctx = None


def _dsn() -> str:
    # LangGraph expects a plain psycopg DSN, not a SQLAlchemy URL
    return settings.DATABASE_URL_SYNC.replace("postgresql+psycopg://", "postgresql://")


async def init_checkpointer() -> AsyncPostgresSaver:
    global _checkpointer, _checkpointer_ctx
    _checkpointer_ctx = AsyncPostgresSaver.from_conn_string(_dsn())
    _checkpointer = await _checkpointer_ctx.__aenter__()
    await _checkpointer.setup()
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _checkpointer_ctx
    if _checkpointer_ctx is not None:
        await _checkpointer_ctx.__aexit__(None, None, None)
        _checkpointer = None
        _checkpointer_ctx = None


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialised. Call init_checkpointer() at startup.")
    return _checkpointer
