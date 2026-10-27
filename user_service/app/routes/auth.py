from fastapi import APIRouter, HTTPException, status

from app.auth import create_access_token, hash_password, verify_password, CurrentUser
from app.broker import BrokerUnavailable, publish_user_registered
from app.deps import UserRepoDep
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def register(body: RegisterRequest, users: UserRepoDep) -> UserRead:
    if await users.get_by_username(body.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    user = await users.add(
        username=body.username,
        password_hash=hash_password(body.password),
    )
    try:
        await publish_user_registered(user_id=user.id, username=user.username)
    except BrokerUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Broker unavailable",
        ) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, users: UserRepoDep) -> TokenResponse:
    user = await users.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(user_id=user.id, username=user.username)
    return TokenResponse(access_token=token)

@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)