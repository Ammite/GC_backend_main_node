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
    role: str | None = None
    name: str | None = None

class ChangePasswordRequest(BaseModel):
    employee_id: int
    new_password: str
