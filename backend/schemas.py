from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# Auth Schemas
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "doctor"

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserOut(BaseModel):
    user_id: int
    username: str
    role: str

    class Config:
        from_attributes = True

# History Schemas
class SearchHistoryOut(BaseModel):
    id: int
    user_id: int
    query: str
    created_at: datetime

    class Config:
        from_attributes = True

# Utility Schemas
class SymptomSuggest(BaseModel):
    symptom_id: str
    symptom_name: str
