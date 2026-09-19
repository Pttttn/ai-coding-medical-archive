import asyncio

import uvicorn

from .main import create_app, create_mcp, get_services


async def main():
    services = get_services()
    settings = services.settings
    internal = uvicorn.Server(uvicorn.Config(create_app(services), host=settings.bind_host,
                                            port=settings.internal_port, log_level="warning", access_log=False))
    # Separate listeners: public MCP cannot route into /internal endpoints.
    await asyncio.gather(internal.serve(), create_mcp(services).run_async(transport="http",
        host=settings.bind_host, port=settings.mcp_port, path="/mcp", show_banner=False,
        uvicorn_config={"log_level": "warning", "access_log": False}))


if __name__ == "__main__":
    asyncio.run(main())

