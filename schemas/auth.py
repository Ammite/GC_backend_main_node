from pydantic import BaseModel


class LoginRequest(BaseModel):
    login: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    user_id: int | None = None
    access_token: str | None = None
    token_type: str | None = None
