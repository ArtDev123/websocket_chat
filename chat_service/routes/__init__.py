from app.routes import messages, rooms, ws


def register_routes(app) -> None:
    app.include_router(rooms.router)
    app.include_router(messages.router)
    app.include_router(ws.router)