from app.db.base import Base
from app.db.session import aengine


async def init_db() -> None:
    async with aengine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
