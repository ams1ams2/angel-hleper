"""
حالات الشخصية - الملاك المساعد
================================
"""

from enum import Enum


class AngelState(Enum):
    """حالات الملاك المختلفة"""
    IDLE = "idle"
    TALKING = "talking"
    HAPPY = "happy"
    HELPING = "helping"
    ALERT = "alert"
    SLEEPING = "sleeping"


def classify_state_from_text(text: str) -> AngelState:
    """تحديد حالة الملاك بناءً على النص"""
    t = (text or "").strip()
    if not t:
        return AngelState.IDLE
    
    alert_keys = ["⚠️", "تحذير", "خطر", "تنبيه", "انتبه", "مشكلة", "خطأ", "أمان", "خصوصية"]
    help_keys = ["اختصار", "جرّب", "اضغط", "استخدم", "فعّل", "سريع", "تقدر", "بدّل", "ميزة", "وفّر", "رتّب", "حل"]
    
    if any(k in t for k in alert_keys):
        return AngelState.ALERT
    if any(k in t for k in help_keys):
        return AngelState.HELPING
    
    return AngelState.TALKING
