import argparse
import asyncio
import sys

import uvicorn


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy().new_event_loop()
    return asyncio.SelectorEventLoop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GeniusTrader FastAPI development server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn reload mode")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        loop="app.cli.run_dev:selector_loop_factory",
        reload=not args.no_reload,
    )


if __name__ == "__main__":
    main()
