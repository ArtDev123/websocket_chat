from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=True)


class TokenUser(BaseModel):
    """Пользователь из подписи JWT. В таблице чата его может ещё не быть."""

    id: int
    username: str


def decode_token_payload(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def decode_token(token: str) -> dict:
    try:
        return decode_token_payload(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials, Depends(bearer_scheme)
    ],
) -> TokenUser:
    payload = decode_token(credentials.credentials)
    return TokenUser(id=int(payload["sub"]), username=str(payload["username"]))


CurrentUser = Annotated[TokenUser, Depends(get_current_user)]