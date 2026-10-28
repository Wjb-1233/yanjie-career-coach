from typing import Literal

from pydantic import EmailStr, Field

from app.core.schemas import ApiModel


class RegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: str = Field(min_length=1, max_length=60, alias="displayName")


class LoginRequest(ApiModel):
    email: EmailStr
    password: str


class DemoLoginRequest(ApiModel):
    role: Literal["STUDENT", "ADMIN"]


class ProfileUpdateRequest(ApiModel):
    display_name: str = Field(min_length=1, max_length=60, alias="displayName")
    bio: str | None = Field(default=None, max_length=500)


class UserView(ApiModel):
    id: str
    email: str
    display_name: str
    role: str
    bio: str | None

    @classmethod
    def from_orm_user(cls, user: object) -> "UserView":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            bio=user.bio,
        )


class AuthResponse(ApiModel):
    access_token: str
    expires_in: int
    user: UserView

