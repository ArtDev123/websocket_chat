import asyncio, json, os
import websockets

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJzdHJpbmciLCJleHAiOjE3OTE1Njc4NTB9.EdZ3ftb7hN2yYiU-FDGNPUlpi06Vleu_rPO6oOFdsQU"
TOKEN_2 = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwidXNlcm5hbWUiOiJzdHJpbmcyIiwiZXhwIjoxNzkxNTY5Njk0fQ.e6ee-qS-6seKAwdHWdBWbi2E1wnBxIVv3mvZTkTd5MI"


async def join_room(websocket):
    await websocket.send(json.dumps({"type": "join", "room_id": 1}))
    print(await websocket.recv())


async def send_message(websocket, text):
    await websocket.send(json.dumps({"type": "dm", "text": text, "to_user_id": 2}))


async def main():
    uri_1 = f"ws://127.0.0.1:8080/ws?token={TOKEN}"
    uri_2 = f"ws://127.0.0.1:8080/ws?token={TOKEN_2}"

    async with websockets.connect(uri_1) as ws_1, websockets.connect(uri_2) as ws_2:
        print(await ws_1.recv())
        print(await ws_2.recv())

        # await join_room(ws_1)
        # await join_room(ws_2)

        await send_message(ws_1, "user_1 message")

        print(await ws_2.recv())
        print(await ws_1.recv())

asyncio.run(main())
