import sys
import uvicorn
import config
from api import app  # noqa: F401 — import triggers lifespan registration

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
    )
