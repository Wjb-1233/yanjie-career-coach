from typing import Literal

from pydantic import EmailStr, Field

from app.core.schemas import ApiModel


class RegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: str = Field(min_length=1, max_length=60, alias="displayName")
    # 注册必须显式勾选《隐私政策》，缺省视为未同意
    consent: bool = False


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
    avatar: str | None = None
    email_verified: bool = True
    created_at: str | None = None

    @classmethod
    def from_orm_user(cls, user: object) -> "UserView":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            bio=user.bio,
            avatar=getattr(user, "avatar", None),
            email_verified=getattr(user, "email_verified", True),
            created_at=user.created_at.isoformat() if getattr(user, "created_at", None) else None,
        )


class AuthResponse(ApiModel):
    access_token: str
    expires_in: int
    user: UserView


class PasswordChangeRequest(ApiModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordRequestInput(ApiModel):
    email: EmailStr


class AvatarRequest(ApiModel):
    data_url: str = Field(min_length=32, max_length=400000)


class AccountDeleteRequest(ApiModel):
    password: str = Field(min_length=8, max_length=72)
    confirm: str = Field(max_length=10)


class PasswordResetRequest(ApiModel):
    email: str = Field(min_length=3, max_length=254)


class PasswordResetConfirm(ApiModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=8, max_length=72)


class VerifyEmailConfirm(ApiModel):
    token: str = Field(min_length=10, max_length=2000)
