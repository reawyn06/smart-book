import json

def extract_ai_text(response) -> str:
    """Chuẩn hóa output của LangChain Gemini thành string."""
    content = response.content

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text = "".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and "text" in block
        )
        return text.strip()

    return str(content).strip()

def extract_json(response):
    """Trích xuất và parse JSON từ response của Gemini"""
    text = extract_ai_text(response)

    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return json.loads(text.strip())