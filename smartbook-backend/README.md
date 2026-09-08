# SmartBook Backend API

Hệ thống Backend mạnh mẽ cho ứng dụng đọc sách thông minh SmartBook. Dự án được xây dựng bằng **FastAPI**, tích hợp quản lý cơ sở dữ liệu với **PostgreSQL (pgvector)**, bộ nhớ đệm **Redis** và ứng dụng Trí tuệ Nhân tạo (**Gemini LLM & LangChain**) để mang lại trải nghiệm cá nhân hóa sâu sắc cho người dùng.

## Các tính năng cốt lõi
* **Authentication:** Xác thực người dùng bảo mật thông qua JWT (JSON Web Tokens).
* **Quản trị Sách & Dữ liệu:** Tự động tìm kiếm và import dữ liệu từ Google Books API, đồng bộ nội dung HTML từ Project Gutenberg.
* **Tích hợp AI & RAG:** Trích xuất văn bản (Chunking), nhúng vector (Local Embedding với `BAAI/bge-base-en-v1.5`), và trò chuyện trực tiếp với sách thông qua Gemini.
* **Hệ thống Đề xuất AI:** Gợi ý sách thông minh dựa trên lịch sử đọc, đánh giá, sở thích cá nhân.
* **Thư viện cá nhân:** Lưu trữ tiến độ đọc, highlight đoạn văn, ghi chú và quản lý danh sách yêu thích.

##  Yêu cầu hệ thống
* Hệ điều hành Windows có hỗ trợ ảo hóa (Virtualization) ở cấp độ CPU.
* **Python 3.9+** (Đề xuất dùng Pycharm).
* **DBeaver** để quản lý cơ sở dữ liệu trực quan.
* (Tùy chọn) **Docker Desktop** nếu muốn tự chạy Database Local.

---

## Hướng dẫn làm việc nhóm 

Dự án hiện đang sử dụng cơ sở dữ liệu dùng chung trên đám mây (**Supabase**) để đảm bảo dữ liệu được đồng bộ liên tục 24/7 cho toàn bộ nhóm.

### 1. Cài đặt biến môi trường (Bắt buộc)
* Sau khi clone code từ GitHub về, liên hệ Trưởng nhóm để lấy nội dung cấu hình bảo mật.
* Tạo một file có tên **`.env`** tại thư mục gốc của dự án (cùng cấp với `main.py`).
* Dán nội dung được cung cấp vào file `.env`. (Bao gồm `DATABASE_URL` trỏ về Supabase, `SECRET_KEY`, `GOOGLE_API_KEY`, và `GEMINI_API_KEY`).
>  **CẢNH BÁO BẢO MẬT:** Tuyệt đối không commit/push file `.env` lên GitHub để tránh lộ thông tin máy chủ. Hệ thống đã có sẵn `.gitignore` để bỏ qua file này.

### 2. Truy cập Database trực tiếp qua DBeaver
Nếu bạn được phân công quản lý dữ liệu, kiểm tra bảng hoặc test query, hãy kết nối DBeaver với các thông số sau:
* **Host:** `db.whqugqesddonlqgwyayr.supabase.co`
* **Port:** `5432`
* **Database:** `postgres`
* **Username:** `postgres`
* **Password:** 

---

## 🛠Hướng dẫn cài đặt & Khởi chạy Server

### Bước 1: Thiết lập môi trường Python
1. Mở Terminal tại thư mục gốc dự án.
2. Tạo môi trường ảo (Virtual Environment):
   ```bash
   python -m venv venv
   ```
3. Kích hoạt môi trường ảo:
   ```bash
   # Trên Windows:
   .\venv\Scripts\activate
   
   # Trên MacOS/Linux:
   source venv/bin/activate
   ```
4. Cài đặt các thư viện phụ thuộc:
   ```bash
   pip install -r requirements.txt
   ```

### Bước 2: Khởi động FastAPI
1. Đảm bảo bạn đã kích hoạt môi trường ảo `(venv)` và đã có file `.env`.
2. Chạy lệnh khởi động server:
   ```bash
   uvicorn main:app --reload
   ```
3. Truy cập vào tài liệu API tương tác (Swagger UI) tại trình duyệt: 
 **`http://127.0.0.1:8000/docs`**

---

## Khởi tạo Database Local bằng Docker
Nếu bạn muốn chạy một database tách biệt hoàn toàn trên máy cá nhân để vọc vạch mà không ảnh hưởng đến dữ liệu chung của nhóm:

1. Sửa `DATABASE_URL` trong file `.env` thành:
   `postgresql://admin:secretpassword@localhost:5432/smartbook_db`
2. Mở Docker Desktop.
3. Chạy lệnh:
   ```bash
   docker compose up -d
   ```