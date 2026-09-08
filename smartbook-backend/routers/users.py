from fastapi import APIRouter, Depends
import models, schemas, security

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.get("/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(security.get_current_user)):
    """Lấy thông tin của người dùng đang đăng nhập"""
    return current_user