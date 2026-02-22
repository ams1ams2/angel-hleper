"""
معالجة النصوص - الملاك المساعد
================================
تنظيف وتنسيق النصوص العربية
"""


def _clean_weird_quotes(text: str) -> str:
    """إزالة علامات الاقتباس الغريبة"""
    if not text:
        return ""
    
    rep = {
        """: "", """: "", "„": "", "«": "", "»": "",
        "\"": "", "'": "", "`": "", "´": "", "'": "", "'": "",
        "…": "...",
    }
    for a, b in rep.items():
        text = text.replace(a, b)
    return text


def normalize_one_sentence_ar(text: str) -> str:
    """تنظيف جملة عربية واحدة"""
    text = (text or "")
    text = _clean_weird_quotes(text)
    text = text.replace("\n", " ").replace("\r", " ").strip()
    text = " ".join(text.split())
    
    # أخذ أول جملة فقط
    for sep in ["۔", "!", "؟", "."]:
        if sep in text:
            first = text.split(sep)[0].strip()
            if first:
                text = first
            break
    
    text = text.strip(" ""\"'` ")
    return text[:260].strip()


def normalize_chat_ar(text: str) -> str:
    """تنظيف نص محادثة عربي"""
    text = (text or "")
    text = _clean_weird_quotes(text)
    text = text.replace("\r", "\n")
    
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    out = "\n".join(lines)
    
    return out[:900].strip()


def is_good_suggestion(text: str) -> bool:
    """التحقق من جودة الاقتراح"""
    if not text:
        return False
    if len(text) < 12:
        return False
    
    words = text.split()
    if len(words) < 5:
        return False
    
    banned = {"نعم", "حسنًا", "تمام", "اوكي", "ok", "okay", "تم"}
    if text.strip().lower() in banned:
        return False
    
    return True
