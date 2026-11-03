from app.routes import messages, rooms, ws, profiles


def register_routes(app) -> None:
    app.include_router(rooms.router)
    app.include_router(messages.router)
    app.include_router(ws.router)
    app.include_router(profiles.router)
