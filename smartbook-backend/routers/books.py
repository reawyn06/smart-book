from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
import models
import schemas
from database import get_db
from langchain_google_genai import ChatGoogleGenerativeAI
import security
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy import or_
import json
from ai_utils import extract_json
router = APIRouter(
    prefix="/books",
    tags=["Books"]
)

# 1. API Lấy danh sách toàn bộ sách
@router.get("", response_model=List[schemas.BookResponse])
def get_books(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return db.query(models.Book).offset(skip).limit(limit).all()


# 2. API Tìm kiếm sách
@router.get("/search", response_model=List[schemas.BookResponse])
def search_local_books(keyword: str, db: Session = Depends(get_db)):
    """(USER) Tìm kiếm sách đã có sẵn trong kho của hệ thống (Title, Author, Categories)"""
    # Tìm sách có Tên, Tác giả HOẶC Thể loại chứa từ khóa (không phân biệt hoa thường)
    books = db.query(models.Book).filter(
        or_(
            models.Book.title.ilike(f"%{keyword}%"),
            models.Book.author.ilike(f"%{keyword}%"),
            models.Book.categories.ilike(f"%{keyword}%")  # Thêm dòng này để quét cả thể loại
        )
    ).all()
    return books


@router.get("/author/{author_name}", response_model=List[schemas.BookResponse])
def get_books_by_author(
        author_name: str,
        db: Session = Depends(get_db)
):
    """Lấy danh sách tất cả các sách của một tác giả cụ thể"""
    # Sử dụng ilike để tìm kiếm (tránh lỗi sai khác chữ hoa/chữ thường)
    books = db.query(models.Book).filter(
        models.Book.author.ilike(f"%{author_name}%")
    ).all()

    if not books:
        raise HTTPException(status_code=404, detail="Chưa có sách nào của tác giả này trong hệ thống.")

    return books

@router.post("/{book_id}/chat")
def chat_with_book(
        book_id: str,
        request: schemas.ChatRequest,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    # 1. Kiểm tra sách có tồn tại không
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách.")

    # 2. Nhúng câu hỏi của người dùng bằng LOCAL EMBEDDING (Đồng bộ với process-ai)
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en-v1.5")
    question_vector = embeddings.embed_query(request.question)

    # 3. Semantic Search: Tìm 5 đoạn văn có nội dung gần giống câu hỏi nhất
    top_chunks = db.query(models.BookChunk).filter(
        models.BookChunk.book_id == book_id
    ).order_by(
        models.BookChunk.embedding.cosine_distance(question_vector)
    ).limit(5).all()

    if not top_chunks:
        raise HTTPException(status_code=400, detail="Sách chưa có dữ liệu AI. Vui lòng chạy API process-ai trước.")

    # 4. Gom 5 đoạn văn lại thành một "Tài liệu" (Context)
    context_text = "\n\n---\n\n".join([chunk.content_text for chunk in top_chunks])

    # 5. Lấy lịch sử trò chuyện từ Database
    chat_history = db.query(models.ChatMessage).filter(
        models.ChatMessage.book_id == book_id,
        models.ChatMessage.user_id == current_user.id
    ).order_by(models.ChatMessage.id.desc()).limit(4).all()

    chat_history.reverse()
    history_text = "\n".join([f"{msg.role}: {msg.content}" for msg in chat_history])

    # 6. Viết Prompt nhốt AI vào ngữ cảnh của cuốn sách và lịch sử chat
    prompt = f"""Bạn là một trợ lý ảo thông minh của ứng dụng SmartBook. Dựa vào phần nội dung trích xuất từ sách dưới đây, hãy trả lời câu hỏi của người dùng một cách chính xác. 
    Nếu thông tin không có trong nội dung này, hãy từ chối khéo léo và nói "Tôi không tìm thấy thông tin này trong sách". Không được tự bịa ra kiến thức bên ngoài.

    LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY:
    {history_text}

    NỘI DUNG TRÍCH XUẤT TỪ SÁCH:
    {context_text}

    CÂU HỎI MỚI NHẤT CỦA NGƯỜI DÙNG:
    {request.question}
    """

    # 7. Gọi Gemini để đọc và trả lời (Chỉ dùng Gemini cho phần suy luận LLM, không dùng cho nhúng)
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
        google_api_key=security.GEMINI_API_KEY
    )

    # Lấy kết quả từ AI
    ai_response = llm.invoke(prompt)

    # Gemini/LangChain có thể trả content dưới dạng list[dict]
    ai_content = ai_response.content

    if isinstance(ai_content, list):
        ai_content = "".join(
            item.get("text", "")
            for item in ai_content
            if isinstance(item, dict)
        )

    if not isinstance(ai_content, str):
        ai_content = str(ai_content)

    # Lưu câu hỏi của user
    user_msg = models.ChatMessage(
        book_id=book_id,
        user_id=current_user.id,
        role="user",
        content=request.question
    )

    # Lưu câu trả lời của AI
    ai_msg = models.ChatMessage(
        book_id=book_id,
        user_id=current_user.id,
        role="assistant",
        content=ai_content
    )

    db.add(user_msg)
    db.add(ai_msg)
    db.commit()

    return {
        "answer": ai_content,
        "context_used": len(top_chunks)
    }


@router.get("/{book_id}/chat/history")
def get_chat_history(
    book_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    # Kiểm tra sách tồn tại
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách.")

    messages = (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.book_id == book_id,
            models.ChatMessage.user_id == current_user.id
        )
        .order_by(models.ChatMessage.id.asc())
        .all()
    )

    return {
        "book_id": book_id,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content
            }
            for msg in messages
        ]
    }

@router.delete("/{book_id}/chat/history")
def clear_chat_history(
    book_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.book_id == book_id,
            models.ChatMessage.user_id == current_user.id
        )
        .delete()
    )

    db.commit()

    return {"message": "Đã xóa lịch sử chat."}


@router.get("/{book_id}/read")
def open_book_for_reading(
        book_id: str,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(security.get_current_user)
):
    """Lấy link gốc và tiến độ đọc cũ để mở màn hình Reader"""
    # 1. Lấy thông tin sách
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách.")

    if not book.content_url:
        raise HTTPException(status_code=400, detail="Sách này chưa được đồng bộ nội dung.")

    # 2. Lấy tiến độ đọc từ thư viện cá nhân
    library_entry = db.query(models.Library).filter(
        models.Library.user_id == current_user.id,
        models.Library.book_id == book_id
    ).first()

    # Nếu sách chưa có trong tủ, mặc định tiến độ là 0.0
    progress = library_entry.reading_progress if library_entry else 0.0

    return {
        "book_id": book.id,
        "title": book.title,
        "content_url": book.content_url,
        "saved_progress": progress
    }


@router.get("/{book_id}/similar")
def get_similar_books(
        book_id: str,
        db: Session = Depends(get_db)
):
    """Đề xuất sách tương tự với cuốn đang đọc"""
    target_book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not target_book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách.")

    # Lấy danh sách ứng viên (loại trừ sách hiện tại)
    candidates = db.query(models.Book).filter(models.Book.id != book_id).limit(30).all()
    if not candidates:
        return {"recommendations": []}

    catalog = "\n".join([f"- ID:{b.id} | {b.title} | {b.categories}" for b in candidates])

    prompt = f"""
    Người dùng vừa đọc xong cuốn sách sau:
    - Tên: {target_book.title}
    - Thể loại: {target_book.categories}
    - Mô tả: {str(target_book.description)[:200]}...

    Hãy chọn ra 3 cuốn sách TƯƠNG TỰ nhất từ kho sách dưới đây:
    {catalog}

    Trả về chuỗi JSON thuần (Array):
    [
      {{
        "book_id": "...",
        "reason": "Lý do ngắn gọn (ví dụ: 'Cùng khám phá chủ đề bi kịch cổ điển...')"
      }}
    ]
    """

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=security.GEMINI_API_KEY)
        response = llm.invoke(prompt)

        ai_text = response.content.strip()
        if ai_text.startswith("```json"): ai_text = ai_text[7:]
        if ai_text.startswith("```"): ai_text = ai_text[3:]
        if ai_text.endswith("```"): ai_text = ai_text[:-3]

        recommendations = json.loads(ai_text.strip())

        result = []
        for rec in recommendations:
            book = db.query(models.Book).filter(models.Book.id == rec["book_id"]).first()
            if book:
                result.append({
                    "book_id": book.id,
                    "title": book.title,
                    "thumbnail": book.cover_url,
                    "categories": book.categories,
                    "reason": rec["reason"]
                })

        return {"recommendations": result}
    except Exception as e:
        return {"error": "Lỗi sinh đề xuất.", "details": str(e)}


@router.get("/discover/ai")
def discover_books_by_ai(
        genre: str = Query(..., description="Chủ đề hoặc thể loại muốn khám phá (VD: fantasy, vũ trụ, trinh thám)"),
        db: Session = Depends(get_db)
):
    """Khám phá sách theo chủ đề với sự tư vấn của AI"""
    candidates = db.query(models.Book).limit(50).all()
    catalog = "\n".join([f"- ID:{b.id} | {b.title} | {b.categories}" for b in candidates])

    prompt = f"""
    Người dùng đang muốn tìm kiếm sách với chủ đề/thể loại: "{genre}".

    Hãy lọc qua danh sách sách hiện có và chọn ra 5 cuốn phù hợp nhất với yêu cầu này.

    Danh sách:
    {catalog}

    Trả về chuỗi JSON thuần (Array):
    [
      {{
        "book_id": "...",
        "reason": "Lý do cuốn sách này phù hợp với chủ đề '{genre}'..."
      }}
    ]
    """

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=security.GEMINI_API_KEY)
        response = llm.invoke(prompt)

        # Dùng file utils xử lý lỗi
        recommendations = extract_json(response)

        result = []
        for rec in recommendations:
            book = db.query(models.Book).filter(models.Book.id == rec["book_id"]).first()
            if book:
                result.append({
                    "book_id": book.id,
                    "title": book.title,
                    "author": book.author,        # Đã sửa
                    "thumbnail": book.cover_url,  # Đã sửa
                    "reason": rec["reason"]
                })

        return {"topic": genre, "recommendations": result}
    except Exception as e:
        return {"error": "Lỗi khám phá sách.", "details": str(e)}