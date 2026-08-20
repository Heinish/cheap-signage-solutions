"""Stand-in for a real Pi agent, used to exercise the mainserver's WebSocket
protocol end-to-end without real hardware. Not part of the shipped product."""
import asyncio
import json
import sys

import websockets

TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
SERVER = sys.argv[2] if len(sys.argv) > 2 else "ws://127.0.0.1:8123"


async def main():
    uri = f"{SERVER}/ws/agent?token={TOKEN}"
    async with websockets.connect(uri) as ws:
        print("connected")

        async def heartbeat_loop():
            while True:
                await ws.send(json.dumps({
                    "type": "heartbeat",
                    "status": {
                        "cpu_percent": 12.3,
                        "memory_percent": 40.1,
                        "temperature": 44.2,
                        "current_url": "http://example.com",
                        "uptime": 3600,
                    },
                }))
                await asyncio.sleep(5)

        hb_task = asyncio.create_task(heartbeat_loop())

        try:
            async for raw in ws:
                msg = json.loads(raw)
                print("received:", msg)
                if msg.get("type") == "command":
                    await ws.send(json.dumps({
                        "type": "result",
                        "request_id": msg["request_id"],
                        "success": True,
                        "message": f"fake-agent handled {msg['action']}",
                    }))
        finally:
            hb_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
