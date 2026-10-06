from app.routes import auth, rooms, users, ws


def register_routes(app) -> None:
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(rooms.router)
    app.include_router(ws.router)
