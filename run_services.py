import asyncio
import uvicorn

async def start_servers():
    # First app
    config1 = uvicorn.Config(
        "auth_service.app.main:app",  
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
    server1 = uvicorn.Server(config1)

    # Second app
    config2 = uvicorn.Config(
        "facility_service.app.main:app",  # replace with your actual module:app
        host="0.0.0.0",
        port=8002,
        reload=True,
    )
    server2 = uvicorn.Server(config2)

    # Run both servers concurrently
    await asyncio.gather(
        server1.serve(),
        server2.serve(),
    )

if __name__ == "__main__":
    try:
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        print("\nShutting down servers...")
