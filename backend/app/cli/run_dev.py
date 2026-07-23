import argparse
import asyncio
import sys

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GeniusTrader FastAPI development server")
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn reload mode")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        loop="none",
        reload=not args.no_reload,
    )


if __name__ == "__main__":
    main()
