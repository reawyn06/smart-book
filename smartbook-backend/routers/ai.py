from fastapi import APIRouter, Depends, HTTPException
from langchain_google_genai import ChatGoogleGenerativeAI

import schemas
import security

router = APIRouter(
    prefix="/ai",
    tags=["AI Assistant"],
    dependencies=[Depends(security.get_current_user)]
)


@router.post("/quick-action")
def ai_quick_action(request: schemas.QuickActionRequest):
    """
    AI Quick Action cho đoạn văn được bôi đen:
    - translate: Dịch sang tiếng Việt.
    - summarize: Tóm tắt 2-3 câu.
    - explain: Giải thích ý nghĩa và từ khó.
    """

    # Prompt theo từng hành động
    if request.action == "translate":
        prompt = f"""
Bạn là trợ lý đọc sách SmartBook.

Nhiệm vụ:
- Dịch đoạn văn sau sang tiếng Việt tự nhiên.
- Giữ nguyên ý nghĩa và văn phong.
- Không giải thích, không thêm nhận xét.
- Chỉ trả về bản dịch.

Đoạn văn:
{request.text}
"""

    elif request.action == "summarize":
        prompt = f"""
Bạn là trợ lý đọc sách SmartBook.

Nhiệm vụ:
- Tóm tắt đoạn văn trong tối đa 3 câu.
- Chỉ nêu ý chính.
- Không thêm thông tin ngoài đoạn văn.

Đoạn văn:
{request.text}
"""

    elif request.action == "explain":
        prompt = f"""
Bạn là trợ lý đọc sách SmartBook.

Nhiệm vụ:
- Giải thích ý nghĩa đoạn văn.
- Giải thích từ khó hoặc ngữ cảnh nếu cần.
- Không bịa thêm nội dung ngoài đoạn văn.

Đoạn văn:
{request.text}
"""

    else:
        raise HTTPException(
            status_code=400,
            detail="Hành động không hợp lệ. Chỉ hỗ trợ: translate, summarize, explain."
        )

    # Gọi Gemini
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
        google_api_key=security.GEMINI_API_KEY,
        temperature=0.2,
    )

    ai_response = llm.invoke(prompt)

    # Lấy text từ LangChain (hỗ trợ cả string và list block)
    if isinstance(ai_response.content, str):
        ai_text = ai_response.content.strip()

    elif isinstance(ai_response.content, list):
        ai_text = "".join(
            block.get("text", "")
            for block in ai_response.content
            if isinstance(block, dict)
        ).strip()

    else:
        ai_text = str(ai_response.content).strip()

    return {
        "action": request.action,
        "result": ai_text
    }