import re
from pydantic import BaseModel, EmailStr, field_validator


_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,128}$")


def _validate_password(v: str) -> str:
    if not _PASSWORD_RE.match(v):
        raise ValueError(
            "Le mot de passe doit contenir au moins 8 caractères, une lettre et un chiffre"
        )
    return v


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    display_name: str = ""

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 32:
            raise ValueError("Nom d'utilisateur : 3–32 caractères")
        if not re.match(r"^[A-Za-z0-9_\-]+$", v):
            raise ValueError("Nom d'utilisateur : lettres, chiffres, _ et - uniquement")
        return v

    @field_validator("display_name")
    @classmethod
    def display_name_valid(cls, v: str) -> str:
        if len(v) > 64:
            raise ValueError("Nom affiché : 64 caractères max")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        return _validate_password(v)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    sub: str
    role: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_valid(cls, v: str) -> str:
        return _validate_password(v)
