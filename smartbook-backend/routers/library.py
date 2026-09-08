from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, security
from datetime import datetime, timedelta
from langchain_google_genai import ChatGoogleGenerativeAI
from ai_utils import extract_json

router = APIRouter(
    prefix="/library",
    tags=["User Library"]
)


@router.get("/")
def get_my_library(
        status: Optional[str] = None,
        is_favorite: Optional[bool] = None,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Lấy danh sách tủ sách của người dùng hiện tại (có hỗ trợ lọc)"""
    query = db.query(models.Library).filter(models.Library.user_id == current_user.id)

    if status:
        query = query.filter(models.Library.status == status)
    if is_favorite is not None:
        query = query.filter(models.Library.is_favorite == is_favorite)

    return query.all()


@router.post("/add")
def add_to_library(
        request: schemas.LibraryAddRequest,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Thêm một cuốn sách vào tủ sách cá nhân"""
    # Kiểm tra sách đã có trong thư viện chưa
    existing = db.query(models.Library).filter(
        models.Library.user_id == current_user.id,
        models.Library.book_id == request.book_id
    ).first()

    if existing:
        existing.status = request.status
        db.commit()
        return {"message": "Đã cập nhật trạng thái sách."}

    new_entry = models.Library(
        user_id=current_user.id,
        book_id=request.book_id,
        status=request.status
    )
    db.add(new_entry)
    db.commit()
    return {"message": "Đã thêm vào tủ sách thành công!"}


@router.put("/{book_id}/favorite")
def toggle_favorite(
        book_id: str,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Bật/tắt trạng thái yêu thích (Thả tim) của một cuốn sách"""
    library_entry = db.query(models.Library).filter(
        models.Library.user_id == current_user.id,
        models.Library.book_id == book_id
    ).first()

    if not library_entry:
        # Nếu sách chưa có trong tủ, tự động thêm vào với trạng thái wishlist và thả tim
        library_entry = models.Library(
            user_id=current_user.id,
            book_id=book_id,
            status="wishlist",
            is_favorite=True
        )
        db.add(library_entry)
        msg = "Đã thêm vào Wishlist và đánh dấu Yêu thích!"
    else:
        # Nếu đã có, đảo ngược trạng thái (True thành False, False thành True)
        library_entry.is_favorite = not library_entry.is_favorite
        msg = "Đã cập nhật trạng thái Yêu thích!"

    db.commit()
    return {"message": msg, "is_favorite": library_entry.is_favorite}


@router.post("/highlights")
def save_highlight(
        request: schemas.HighlightRequest,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Lưu lại đoạn văn bôi đen và ghi chú"""
    new_highlight = models.Highlight(
        user_id=current_user.id,
        book_id=request.book_id,
        selected_text=request.selected_text,
        note=request.note
    )
    db.add(new_highlight)
    db.commit()
    return {"message": "Đã lưu ghi chú thành công!"}


@router.put("/{book_id}/progress")
def update_reading_progress(
        book_id: str,
        request: schemas.ProgressUpdate,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Lưu tiến độ đọc sách của người dùng (tính theo %)"""
    library_entry = db.query(models.Library).filter(
        models.Library.user_id == current_user.id,
        models.Library.book_id == book_id
    ).first()

    if not library_entry:
        # Nếu sách chưa có trong tủ, tự động thêm vào với trạng thái đang đọc
        library_entry = models.Library(
            user_id=current_user.id,
            book_id=book_id,
            status="reading",
            reading_progress=request.progress
        )
        db.add(library_entry)
    else:
        # Nếu đã có, chỉ cần cập nhật con số và đổi trạng thái
        library_entry.reading_progress = request.progress
        library_entry.status = "reading"

    db.commit()
    return {
        "message": "Đã lưu tiến độ đọc!",
        "book_id": book_id,
        "progress": request.progress
    }


@router.get("/{book_id}/highlights")
def get_book_highlights(
        book_id: str,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Lấy danh sách các đoạn highlight và ghi chú của cuốn sách"""
    highlights = db.query(models.Highlight).filter(
        models.Highlight.book_id == book_id,
        models.Highlight.user_id == current_user.id
    ).order_by(models.Highlight.id.desc()).all()

    return highlights


@router.delete("/highlights/{highlight_id}")
def delete_highlight(
        highlight_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Xóa một ghi chú/đoạn bôi đen cụ thể"""
    highlight = db.query(models.Highlight).filter(
        models.Highlight.id == highlight_id,
        models.Highlight.user_id == current_user.id
    ).first()

    if not highlight:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy ghi chú hoặc bạn không có quyền xóa ghi chú này."
        )

    db.delete(highlight)
    db.commit()
    return {"message": "Đã xóa ghi chú thành công!"}


@router.delete("/{book_id}")
def remove_from_library(
        book_id: str,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Xóa sách khỏi tủ sách cá nhân"""
    library_entry = db.query(models.Library).filter(
        models.Library.user_id == current_user.id,
        models.Library.book_id == book_id
    ).first()

    if not library_entry:
        raise HTTPException(status_code=404, detail="Sách này không có trong thư viện của bạn.")

    db.delete(library_entry)
    db.commit()

    return {"message": "Đã xóa sách khỏi tủ sách thành công!"}

@router.get("/authors")
def get_favorite_authors(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Lấy danh sách tác giả yêu thích"""
    authors = db.query(models.FavoriteAuthor).filter(
        models.FavoriteAuthor.user_id == current_user.id
    ).all()
    return {"favorite_authors": [a.author_name for a in authors]}


@router.post("/authors")
def add_favorite_author(
        request: schemas.FavoriteAuthorRequest,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Thêm một tác giả vào danh sách yêu thích"""
    existing = db.query(models.FavoriteAuthor).filter(
        models.FavoriteAuthor.user_id == current_user.id,
        models.FavoriteAuthor.author_name.ilike(request.author_name)
    ).first()

    if existing:
        return {"message": "Tác giả này đã có trong danh sách yêu thích."}

    new_author = models.FavoriteAuthor(
        user_id=current_user.id,
        author_name=request.author_name
    )
    db.add(new_author)
    db.commit()
    return {"message": f"Đã thêm {request.author_name} vào danh sách yêu thích!"}


@router.delete("/authors/{author_name}")
def remove_favorite_author(
        author_name: str,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Xóa tác giả khỏi danh sách yêu thích"""
    author = db.query(models.FavoriteAuthor).filter(
        models.FavoriteAuthor.user_id == current_user.id,
        models.FavoriteAuthor.author_name.ilike(author_name)
    ).first()

    if not author:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác giả trong danh sách.")

    db.delete(author)
    db.commit()
    return {"message": f"Đã bỏ theo dõi tác giả {author_name}."}


@router.get("/recommendations")
def get_ai_recommendations(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Đề xuất sách AI cho màn hình Home"""

    cache_valid_time = datetime.utcnow() - timedelta(days=7)

    # ===== CACHE =====
    cached_recs = (
        db.query(models.UserRecommendation)
        .filter(
            models.UserRecommendation.user_id == current_user.id,
            models.UserRecommendation.created_at >= cache_valid_time
        )
        .all()
    )

    if cached_recs:
        result = []
        for rec in cached_recs:
            book = db.query(models.Book).filter(models.Book.id == rec.book_id).first()
            if book:
                result.append({
                    "book_id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "thumbnail": book.cover_url,
                    "categories": book.categories,
                    "reason": rec.reason
                })

        if result:
            return {"recommendations": result, "source": "cache"}

    # ===== XÓA CACHE CŨ =====
    db.query(models.UserRecommendation).filter(
        models.UserRecommendation.user_id == current_user.id
    ).delete()
    db.commit()

    # ===== LẤY DỮ LIỆU USER =====
    my_library = db.query(models.Library).filter(models.Library.user_id == current_user.id).all()
    liked_ids = [b.book_id for b in my_library if b.is_favorite or b.status == "done"]
    owned_ids = [b.book_id for b in my_library]

    liked_books = []
    if liked_ids:
        liked_books = db.query(models.Book).filter(models.Book.id.in_(liked_ids)).all()

    liked_titles = [f"{b.title} ({b.categories})" for b in liked_books]

    query = db.query(models.Book)
    if owned_ids:
        query = query.filter(~models.Book.id.in_(owned_ids))

    available_books = query.limit(30).all()

    if not available_books:
        return {"recommendations": [], "message": "Hệ thống chưa có sách mới."}

    catalog = "\n".join([f"- ID:{b.id} | {b.title} | {b.categories}" for b in available_books])

    fav_authors_db = db.query(models.FavoriteAuthor).filter(
        models.FavoriteAuthor.user_id == current_user.id
    ).all()
    liked_authors = [a.author_name for a in fav_authors_db]

    prompt = f"""
    Bạn là chuyên gia gợi ý sách.

    Người dùng thích các sách:
    {liked_titles if liked_titles else "Chưa có dữ liệu."}

    Tác giả yêu thích của họ là:
    {', '.join(liked_authors) if liked_authors else "Chưa có dữ liệu tác giả."}

    Kho sách hiện có:
    {catalog}

    Chọn đúng 5 cuốn.

    Trả về JSON thuần:
    [
      {{
        "book_id": "...",
        "reason": "..."
      }}
    ]
    """

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            google_api_key=security.GEMINI_API_KEY
        )

        response = llm.invoke(prompt)

        # Dùng file utils xử lý triệt để lỗi
        recommendations = extract_json(response)

        result = []
        seen = set()

        for rec in recommendations:
            if rec["book_id"] in seen:
                continue
            seen.add(rec["book_id"])

            db.add(
                models.UserRecommendation(
                    user_id=current_user.id,
                    book_id=rec["book_id"],
                    reason=rec["reason"]
                )
            )

            book = db.query(models.Book).filter(models.Book.id == rec["book_id"]).first()
            if book:
                result.append({
                    "book_id": book.id,
                    "title": book.title,
                    "author": book.author,  # Đã sửa
                    "thumbnail": book.cover_url,  # Đã sửa
                    "categories": book.categories,
                    "reason": rec["reason"]
                })

        db.commit()

        return {
            "recommendations": result,
            "source": "ai_generated"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi sinh đề xuất AI: {e}")
