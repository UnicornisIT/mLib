from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class AuthStatus(BaseModel):
    setup_required: bool
    authenticated: bool


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Имя пользователя не может быть пустым")
        return normalized


class SetupRequest(Credentials):
    password: str = Field(min_length=15, max_length=200)
    library_path: str | None = None
    import_path: str | None = None


class UserRead(BaseModel):
    id: str
    username: str
    display_name: str | None
    bio: str | None
    location: str | None
    birth_date: date | None
    avatar_color: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=120)
    birth_date: date | None = None
    avatar_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("display_name", "bio", "location", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Дата рождения не может быть в будущем")
        return value


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)
    new_password_confirmation: str = Field(min_length=1, max_length=200)
