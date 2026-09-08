import uuid
from database import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Float
def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="User")
    is_active = Column(Boolean, default=True)


class Book(Base):
    __tablename__ = "books"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    categories = Column(String, default="Chưa phân loại")
    author = Column(String, nullable=False)
    description = Column(String, nullable=True)
    cover_url = Column(String, nullable=True)
    content_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

class BookChunk(Base):
    __tablename__ = "book_chunks"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(String, ForeignKey("books.id", ondelete="CASCADE"))
    chunk_index = Column(Integer)
    content_text = Column(String)
    embedding = Column(Vector(768))
    book = relationship("Book")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(String, ForeignKey("books.id", ondelete="CASCADE"))
    user_id = Column(String, ForeignKey("users.id"))
    role = Column(String)
    content = Column(String)

class Library(Base):
    __tablename__ = "library"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"))
    book_id = Column(String, ForeignKey("books.id", ondelete="CASCADE"))
    status = Column(String, default="Reading")
    reading_progress = Column(Float, default=0.0)
    is_favorite = Column(Boolean, default=False)

class Highlight(Base):
    __tablename__ = "highlights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"))
    book_id = Column(String, ForeignKey("books.id", ondelete="CASCADE"))
    selected_text = Column(String)
    note = Column(String, nullable=True)

class UserRecommendation(Base):
    __tablename__ = "user_recommendations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    book_id = Column(String, ForeignKey("books.id"))
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class FavoriteAuthor(Base):
    __tablename__ = "favorite_authors"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"))
    author_name = Column(String, index=True)