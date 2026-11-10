"""Ручной клиент кадра typing. Сервисы должны быть уже подняты.

Слушать комнату:

    python scripts/ws_typing_check.py --username bob --password secret --room general

Отправить один кадр typing после join:

    python scripts/ws_typing_check.py --username alice --password secret --room general --send
"""

import argparse
import asyncio
import json
import urllib.error
import urllib.request

import websockets


def request(method: str, url: str, payload: dict | None = None, token: str | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def login(user_api: str, username: str, password: str) -> str:
    status, _ = request(
        "POST",
        f"{user_api}/auth/register",
        {"username": username, "password": password},
    )
    if status not in (201, 409):
        raise SystemExit(f"register {username}: {status}")
    status, body = request(
        "POST",
        f"{user_api}/auth/login",
        {"username": username, "password": password},
    )
    if status != 200:
        raise SystemExit(f"login {username}: {status} {body}")
    return body["access_token"]


def room_id(chat_api: str, token: str, name: str) -> int:
    status, rooms = request("GET", f"{chat_api}/rooms", token=token)
    if status != 200:
        raise SystemExit(f"list rooms: {status} {rooms}")
    for room in rooms:
        if room["name"] == name:
            return room["id"]
    status, created = request(
        "POST",
        f"{chat_api}/rooms",
        {"name": name},
        token=token,
    )
    if status != 201:
        raise SystemExit(f"create room: {status} {created}")
    return created["id"]


async def run(args: argparse.Namespace) -> None:
    token = args.token or login(args.user_api, args.username, args.password)
    joined = args.room_id if args.room_id is not None else room_id(args.chat_api, token, args.room)
    url = f"{args.ws}?token={token}"
    async with websockets.connect(url) as ws:
        print("connected", joined, flush=True)
        await ws.send(json.dumps({"type": "join", "room_id": joined}))
        if args.send:
            await ws.send(json.dumps({"type": "typing", "room_id": joined}))
            print("sent typing", joined, flush=True)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + args.seconds
        while loop.time() < deadline:
            timeout = deadline - loop.time()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except TimeoutError:
                break
            print(raw, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка кадра typing")
    parser.add_argument("--user-api", default="http://127.0.0.1:8081")
    parser.add_argument("--chat-api", default="http://127.0.0.1:8082")
    parser.add_argument("--ws", default="ws://127.0.0.1:8082/ws")
    parser.add_argument("--username", default="alice")
    parser.add_argument("--password", default="secret")
    parser.add_argument("--token", default="")
    parser.add_argument("--room", default="general")
    parser.add_argument("--room-id", type=int, default=None)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--seconds", type=float, default=4)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
