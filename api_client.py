"""
تكامل OpenRouter API - الملاك المساعد
=====================================
التواصل مع OpenRouter GPT-5.2
"""

import time
import random
import logging
import requests

from config import OPENROUTER_API_KEY, MODEL, SYSTEM_PROMPT_VISION, SYSTEM_PROMPT_CHAT, reload_api_key
from text_utils import normalize_one_sentence_ar, normalize_chat_ar, is_good_suggestion
from memory import build_personal_memory_prompt

logger = logging.getLogger("AngelAssistant.API")


def _get_api_key():
    """الحصول على API key (ديناميكي)"""
    from config import OPENROUTER_API_KEY
    return OPENROUTER_API_KEY or reload_api_key()


def _openrouter_headers():
    """رؤوس HTTP لـ OpenRouter"""
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("❌ OPENROUTER_API_KEY غير موجود. اضغط F9 لإدخاله.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "AngelAssistant-GPT5.2"
    }


def _extract_text_from_openrouter_json(data: dict) -> str:
    """استخراج النص من استجابة OpenRouter JSON"""
    try:
        if not isinstance(data, dict):
            return ""
        
        choices = data.get("choices", [])
        if not choices:
            return ""
        
        choice0 = choices[0] if isinstance(choices[0], dict) else {}
        msg = choice0.get("message", {}) or {}
        
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
            
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, str) and item.strip():
                        parts.append(item.strip())
                    elif isinstance(item, dict):
                        t = item.get("text") or item.get("content")
                        if isinstance(t, str) and t.strip():
                            parts.append(t.strip())
                if parts:
                    return " ".join(parts).strip()
        
        delta = choice0.get("delta", {})
        if isinstance(delta, dict):
            c = delta.get("content", "")
            if isinstance(c, str) and c.strip():
                return c.strip()
        
        td = choice0.get("text", "")
        if isinstance(td, str) and td.strip():
            return td.strip()
        
        return ""
    except Exception:
        return ""


def ask_openrouter_vision(image_url: str, mem: dict, max_tries: int = 3) -> str:
    """
    طلب اقتراح من OpenRouter بناءً على صورة الشاشة
    
    Args:
        image_url: عنوان الصورة (data URL)
        mem: الذاكرة
        max_tries: عدد المحاولات
    
    Returns:
        الاقتراح المنظف
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = _openrouter_headers()
    
    mem_hint = build_personal_memory_prompt(mem)
    system_prompt = SYSTEM_PROMPT_VISION + ((" " + mem_hint) if mem_hint else "")
    
    user_prompts = [
        "اعطني اقتراحًا واحدًا: إما اختصار مفيد، أو معلومة مدهشة، أو نصيحة ذكية مرتبطة بما يظهر في الصورة. جملة واحدة بالعربية.",
        "اكتب جملة واحدة بالعربية: اقتراح عملي أو حقيقة تدهش المستخدم أو فكرة توفر وقته، بناءً على الصورة.",
        "قدّم اقتراحًا واحدًا بالعربية (جملة واحدة): يمكن أن يكون اختصارًا، معلومة غريبة، أو تنبيهًا ذكيًا حسب الصورة.",
        "انظر إلى المحتوى المعروض (يوتيوب، مقال، دورة، إلخ). إن كان المستخدم يتابع موضوعاً معيّناً (مثلاً LLM أو AI)، أعطه معلومة مهمة أو حصرية عن نفس الموضوع في جملة واحدة بالعربية."
    ]
    
    last_raw = ""
    last_err = None
    
    for attempt in range(max_tries):
        try:
            payload = {
                "model": MODEL,
                "temperature": 0.7 + (0.15 * attempt),
                "max_tokens": 650,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": random.choice(user_prompts)},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
            }
            
            r = requests.post(url, headers=headers, json=payload, timeout=90)
            r.raise_for_status()
            data = r.json()
            
            raw = _extract_text_from_openrouter_json(data)
            last_raw = raw
            
            if not raw or not raw.strip():
                time.sleep(0.8 + attempt * 0.5)
                continue
            
            cleaned = normalize_one_sentence_ar(raw)
            if is_good_suggestion(cleaned):
                return cleaned
            
            last_err = f"weak attempt={attempt+1}"
            time.sleep(0.8 + attempt * 0.5)
        
        except requests.exceptions.RequestException as e:
            last_err = f"Request error: {str(e)}"
            time.sleep(1.0 + attempt * 0.7)
        except Exception as e:
            last_err = f"Unexpected error: {str(e)}"
            time.sleep(1.0 + attempt * 0.7)
    
    # Fallback
    if last_raw and len(last_raw.strip()) > 10:
        fb = normalize_one_sentence_ar(last_raw)
        if len(fb) >= 15:
            return fb
    
    logger.warning("⚠️ فشل Vision: %s", last_err)
    fallbacks = [
        "جرّب Ctrl+L للانتقال لشريط العنوان بسرعة وتختصر وقتك ⚡",
        "استخدم Ctrl+Tab للتنقل بين النوافذ المفتوحة بسرعة 🚀",
        "اضغط Win+D لإظهار سطح المكتب والعودة إليه بسرعة ⚡",
        "استخدم Ctrl+Shift+T لاستعادة آخر تبويب مغلق 🎯"
    ]
    return random.choice(fallbacks)


def ask_openrouter_chat(user_text: str, mem: dict, max_tries: int = 2) -> str:
    """
    طلب رد محادثة من OpenRouter
    
    Args:
        user_text: نص المستخدم
        mem: الذاكرة
        max_tries: عدد المحاولات
    
    Returns:
        الرد المنظف
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = _openrouter_headers()
    
    # سياق خفيف من الذاكرة
    chat_hist = mem.get("chat_history", []) or []
    chat_hist = chat_hist[-6:]
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT_CHAT}]
    for item in chat_hist:
        if isinstance(item, dict) and "role" in item and "content" in item:
            messages.append({"role": item["role"], "content": item["content"]})
    
    messages.append({"role": "user", "content": (user_text or "").strip()})
    
    last_raw = ""
    for attempt in range(max_tries):
        try:
            payload = {
                "model": MODEL,
                "temperature": 0.55 + (0.1 * attempt),
                "max_tokens": 900,
                "messages": messages
            }
            
            r = requests.post(url, headers=headers, json=payload, timeout=90)
            r.raise_for_status()
            data = r.json()
            
            raw = _extract_text_from_openrouter_json(data)
            last_raw = raw
            if raw and raw.strip():
                return normalize_chat_ar(raw)
        
        except Exception:
            time.sleep(0.6 + attempt * 0.6)
    
    # Fallback
    if last_raw:
        return normalize_chat_ar(last_raw)
    
    return "تمام 👍 اكتب لي هدفك بالضبط (وش تبغى تسوي؟) وأنا أعطيك خطوات مباشرة ✨"
