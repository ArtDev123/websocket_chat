from app.routes import auth, users


def register_routes(app) -> None:
    app.include_router(auth.router)
    app.include_router(users.router)
