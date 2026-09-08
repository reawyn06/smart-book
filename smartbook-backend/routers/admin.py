from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import requests
from bs4 import BeautifulSoup
from typing import List
import models, schemas, security
from database import get_db
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

# 1. KHÓA TOÀN BỘ ROUTER BẰNG QUYỀN ADMIN
router = APIRouter(
    prefix="/admin",
    tags=["Admin Panel"],
    dependencies=[Depends(security.get_current_admin_user)]
)

@router.get("/books/search/google", response_model=List[schemas.GoogleBookResult])
def search_google_books(keyword: str, max_results: int = 5):
    """Tìm sách từ Google Books API để chuẩn bị Import"""
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": keyword, "maxResults": max_results, "key": security.GOOGLE_API_KEY}
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Lỗi khi gọi Google Books API.")

    data = response.json()
    results = []
    for item in data.get("items", []):
        volume_info = item.get("volumeInfo", {})
        authors = volume_info.get("authors", ["Không rõ tác giả"])
        categories = volume_info.get("categories", ["Chưa phân loại"])
        image_links = volume_info.get("imageLinks", {})

        book = schemas.GoogleBookResult(
            id=item.get("id"),
            title=volume_info.get("title", "Không có tiêu đề"),
            author=", ".join(authors),
            categories=", ".join(categories),
            description=volume_info.get("description"),
            cover_url=image_links.get("thumbnail")
        )
        results.append(book)
    return results


@router.post("/books/import/{google_book_id}",response_model=schemas.BookResponse,status_code=status.HTTP_201_CREATED)
def import_book_from_google(
    google_book_id: str,
    db: Session = Depends(get_db)
):
    """Import sách từ Google Books theo ID (có fallback lấy category)."""
    # 1. Kiểm tra sách đã tồn tại chưa
    db_book = db.query(models.Book).filter(
        models.Book.id == google_book_id
    ).first()

    if db_book:
        raise HTTPException(status_code=400, detail="Cuốn sách này đã tồn tại.")

    # 2. Gọi Google Books API theo ID
    url = f"https://www.googleapis.com/books/v1/volumes/{google_book_id}"

    response = requests.get(
        url,
        params={"key": security.GOOGLE_API_KEY}
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy dữ liệu sách trên Google Books."
        )

    volume_info = response.json().get("volumeInfo", {})

    title = volume_info.get("title", "Không có tiêu đề")

    # ===== Tác giả =====
    raw_authors = volume_info.get("authors")
    if raw_authors and isinstance(raw_authors, list):
        author_str = ", ".join(raw_authors)
    else:
        author_str = "Không rõ tác giả"

    # ===== Thể loại =====
    raw_categories = volume_info.get("categories")

    # Fallback nếu API chi tiết không có categories
    if not raw_categories:
        search_response = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={
                "q": f'intitle:"{title}"',
                "maxResults": 5,
                "key": security.GOOGLE_API_KEY
            }
        )

        if search_response.status_code == 200:
            items = search_response.json().get("items", [])

            # Ưu tiên đúng Google Book ID
            for item in items:
                if item.get("id") == google_book_id:
                    raw_categories = item.get("volumeInfo", {}).get("categories")
                    break

            # Nếu vẫn chưa có thì lấy kết quả đầu tiên có category
            if not raw_categories:
                for item in items:
                    cat = item.get("volumeInfo", {}).get("categories")
                    if cat:
                        raw_categories = cat
                        break

    if raw_categories and isinstance(raw_categories, list):
        categories_str = ", ".join(raw_categories)
    else:
        categories_str = "Chưa phân loại"

    # ===== Lưu Database =====
    new_book = models.Book(
        id=google_book_id,
        title=title,
        author=author_str,
        categories=categories_str,
        description=volume_info.get("description"),
        cover_url=volume_info.get("imageLinks", {}).get("thumbnail"),
        content_url=None
    )

    db.add(new_book)
    db.commit()
    db.refresh(new_book)

    return new_book

@router.post("/books/{book_id}/sync-gutenberg/{gutenberg_id}", response_model=schemas.BookResponse)
def sync_book_content_from_gutenberg(book_id: str, gutenberg_id: int, db: Session = Depends(get_db)):
    """Đồng bộ dữ liệu HTML từ Project Gutenberg"""
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách trong hệ thống.")

    html_url = f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}-images.html"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.head(html_url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Mã Gutenberg ID không hợp lệ hoặc không có bản HTML.")

    book.content_url = html_url
    db.commit()
    db.refresh(book)
    return book


@router.post("/books/{book_id}/process-ai")
def process_book_for_ai(book_id: str, db: Session = Depends(get_db)):
    """Chạy Pipeline AI (Chunking + Embedding)"""
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book or not book.content_url:
        raise HTTPException(status_code=400, detail="Sách chưa có URL nội dung.")

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(book.content_url, headers=headers)

    soup = BeautifulSoup(response.text, 'lxml')
    text_content = soup.get_text(separator='\n', strip=True)

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, length_function=len)
    chunks = text_splitter.split_text(text_content)

    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en-v1.5")
    db.query(models.BookChunk).filter(models.BookChunk.book_id == book_id).delete()
    db.commit()

    vectors = embeddings.embed_documents(chunks)
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        db.add(models.BookChunk(book_id=book_id, chunk_index=idx, content_text=chunk, embedding=vector))
    db.commit()

    return {"message": "Xử lý AI thành công bằng Local Embedding!", "total_chunks": len(chunks)}


@router.post("/books/{book_id}/search-debug")
def debug_semantic_search(
        book_id: str,
        request: schemas.ChatRequest,
        db: Session = Depends(get_db)
        # Không cần gọi Depends(admin) ở đây vì Router đã khóa mặc định ở đầu file
):
    """(ADMIN) Debug luồng RAG: Xem trước các Chunk được trích xuất"""
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en-v1.5")
    question_vector = embeddings.embed_query(request.question)

    top_chunks = db.query(models.BookChunk).filter(
        models.BookChunk.book_id == book_id
    ).order_by(
        models.BookChunk.embedding.cosine_distance(question_vector)
    ).limit(3).all()

    results = []
    for chunk in top_chunks:
        results.append({
            "chunk_index": chunk.chunk_index,
            "preview": chunk.content_text[:200] + "..."
        })

    return {"query": request.question, "chunks_found": len(results), "chunks": results}



@router.delete("/books/{book_id}")
def admin_delete_book(book_id: str, db: Session = Depends(get_db)):
    """Xóa sách khỏi toàn bộ database"""
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Không tìm thấy sách cần xóa.")

    db.delete(book)
    db.commit()
    return {"message": f"Đã xóa thành công sách {book_id} khỏi hệ thống."}