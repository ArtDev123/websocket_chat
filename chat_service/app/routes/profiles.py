from fastapi import APIRouter

from app.auth import CurrentUser
from app.deps import ProfileRepoDep
from app.schemas import ProfileRead

router = APIRouter(tags=["profiles"])


@router.get("/profiles", response_model=list[ProfileRead])
async def list_profiles(
    profiles: ProfileRepoDep,
    _: CurrentUser,
) -> list[ProfileRead]:
    rows = await profiles.get_all()
    return [ProfileRead.model_validate(row) for row in rows]
