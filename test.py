import asyncio, json, os
import websockets

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJzdHJpbmciLCJleHAiOjE3OTEzOTcxMDN9.GwV0k6KyAQce1QTFPGB5xctLVyFY23QnfZuv5Dy3Kag"

async def main():
    uri = f"ws://127.0.0.1:8080/ws?token={TOKEN}"
    async with websockets.connect(uri) as ws:
        print(await ws.recv())
        await ws.send(json.dumps({"type": "join", "room_id": 1}))
        print(await ws.recv())
        await ws.send(json.dumps({"type": "leave", "room_id": 1}))
        print(await ws.recv())

asyncio.run(main())

