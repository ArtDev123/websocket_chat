from typing import Annotated

from fastapi import Depends

from app.db import SessionDep
from app.repositories.users import UserRepository


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
