from fastapi import FastAPI
import models
from database import engine
from routers import books,auth, users, library, admin, ai
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartBook API", description="Backend cho hệ thống SmartBook")
@app.on_event("startup")
async def startup():
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        # Khởi tạo kết nối tới Redis
        redis = aioredis.from_url(redis_url, encoding="utf8", decode_responses=True)
        FastAPICache.init(RedisBackend(redis), prefix="smartbook-cache")
        print(" Đã kết nối Redis Cache thành công!")
    else:
        print("⚠Cảnh báo: Không tìm thấy REDIS_URL trong file .env")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(books.router)
app.include_router(library.router)
app.include_router(ai.router)
app.include_router(admin.router)