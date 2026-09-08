from pydantic import BaseModel, EmailStr
from typing import Literal

class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None

class BookCreate(BaseModel):
    id: str
    title: str
    author: str
    description: str | None = None
    cover_url: str | None = None
    content_url: str | None = None

class BookResponse(BaseModel):
    id: str
    title: str
    author: str
    categories: str | None = "Chưa phân loại"
    description: str | None
    cover_url: str | None
    content_url: str | None
    is_active: bool

    class Config:
        from_attributes = True

class GoogleBookResult(BaseModel):
    id: str
    title: str
    author: str
    categories: str | None = "Chưa phân loại"
    description: str | None = None
    cover_url: str | None = None

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    context_used: int

class LibraryAddRequest(BaseModel):
    book_id: str
    status: str = "Reading"

class HighlightRequest(BaseModel):
    book_id: str
    selected_text: str
    note: str = None

class ProgressUpdate(BaseModel):
    progress: float

class QuickActionRequest(BaseModel):
    action: Literal["translate", "summarize", "explain"]
    text: str

class FavoriteAuthorRequest(BaseModel):
    author_name: str