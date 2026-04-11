from pydantic import BaseModel

class UserRegister(BaseModel):
    username: str
    password: str
    role: str = "doctor"

class Token(BaseModel):
    access_token: str
    token_type: str

class UserOut(BaseModel):
    user_id: str
    username: str
    role: str

    class Config:
        from_attributes = True
