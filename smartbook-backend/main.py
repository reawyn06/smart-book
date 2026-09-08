from fastapi import FastAPI
import models
from database import engine
from routers import books,auth, users, library, admin, ai
from fastapi.middleware.cors import CORSMiddleware

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartBook API", description="Backend cho hệ thống SmartBook")

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