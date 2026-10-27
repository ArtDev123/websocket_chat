from fastapi import APIRouter

from app.auth import CurrentUser
from app.deps import UserRepoDep
from app.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
async def list_users(
    users: UserRepoDep,
    _: CurrentUser,
) -> list[UserRead]:
    rows = await users.get_all()
    return [UserRead.model_validate(u) for u in rows]
