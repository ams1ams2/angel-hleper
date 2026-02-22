"""
نظام الذاكرة - الملاك المساعد
==============================
إدارة الذاكرة الممتدة والملف الشخصي للمستخدم
"""

import os
import json
import logging
from config import MEMORY_PATH, MAX_HISTORY, MAX_RECENT_HINTS

logger = logging.getLogger("AngelAssistant.Memory")


def load_memory() -> dict:
    """تحميل الذاكرة من ملف JSON"""
    base = {
        "user_profile": {
            "top_window_keywords": {},
            "hot_apps": {},
            "style_prefs": {
                "prefer_shortcuts": True,
                "prefer_warnings": True,
                "tone": "confident"
            }
        },
        "history": [],
        "last_suggestion": "",
        "last_topics": [],
        "chat_history": []
    }
    
    if not os.path.exists(MEMORY_PATH):
        return base
    
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return base
        for k, v in base.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return base


def save_memory(mem: dict) -> None:
    """حفظ الذاكرة إلى ملف JSON"""
    try:
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("⚠️ فشل حفظ الذاكرة: %s", e)


def _tokenize_title(title: str) -> list[str]:
    """تقسيم عنوان النافذة إلى كلمات"""
    if not title:
        return []
    t = title.replace("-", " ").replace("|", " ").replace("—", " ").replace("_", " ")
    tokens = [x.strip().lower() for x in t.split()]
    tokens = [x for x in tokens if len(x) >= 4 and not x.isdigit()]
    return tokens[:12]


def update_profile_from_window(mem: dict, window_title: str) -> None:
    """تحديث الملف الشخصي بناءً على النافذة النشطة"""
    if not window_title:
        return
    
    up = mem.setdefault("user_profile", {})
    kw = up.setdefault("top_window_keywords", {})
    apps = up.setdefault("hot_apps", {})
    
    tokens = _tokenize_title(window_title)
    for tok in tokens[:8]:
        kw[tok] = int(kw.get(tok, 0)) + 1
    
    app_name = " ".join(tokens[:2]) if tokens else ""
    if app_name:
        apps[app_name] = int(apps.get(app_name, 0)) + 1


def remember_topic(mem: dict, suggestion: str) -> None:
    """حفظ موضوع الاقتراح في الذاكرة"""
    if not suggestion:
        return
    
    topics = mem.setdefault("last_topics", [])
    keys = ["اختصار", "ميزة", "تنبيه", "خصوصية", "أمان", "بحث", "تبويب", "إعدادات", "تركيز", "تنظيم"]
    found = [k for k in keys if k in suggestion]
    
    if not found:
        return
    
    for f in found:
        topics.append(f)
    mem["last_topics"] = topics[-MAX_RECENT_HINTS:]


def build_personal_memory_prompt(mem: dict) -> str:
    """بناء prompt مخصص بناءً على الذاكرة"""
    up = mem.get("user_profile", {})
    kw = up.get("top_window_keywords", {}) or {}
    apps = up.get("hot_apps", {}) or {}
    
    top_kw = sorted(kw.items(), key=lambda x: x[1], reverse=True)[:6]
    top_apps = sorted(apps.items(), key=lambda x: x[1], reverse=True)[:3]
    
    kw_str = ", ".join([k for k, _ in top_kw]) if top_kw else ""
    app_str = ", ".join([a for a, _ in top_apps]) if top_apps else ""
    
    last = (mem.get("last_suggestion") or "").strip()
    last_topics = mem.get("last_topics", []) or []
    topics_str = ", ".join(last_topics[-6:]) if last_topics else ""
    
    parts = []
    if app_str:
        parts.append(f"أكثر تطبيقات تظهر للمستخدم: {app_str}.")
    if kw_str:
        parts.append(f"كلمات سياق متكررة: {kw_str}.")
    if topics_str:
        parts.append(f"مواضيع حديثة: {topics_str}.")
    if last:
        parts.append(f"تجنب تكرار نفس الفكرة السابقة حرفيًا: ({last}).")
    
    return " ".join(parts).strip()
