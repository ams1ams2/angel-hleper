"""
وظائف مساعدة - الملاك المساعد
==============================
دوال utility للتقاط الشاشة، التشفير، والنوافذ
"""

import base64
import hashlib
from io import BytesIO
import mss
from PIL import Image

from config import MONITOR_INDEX


def capture_screen_png() -> bytes:
    """التقاط الشاشة وإرجاعها كـ PNG bytes"""
    with mss.mss() as sct:
        monitor = sct.monitors[MONITOR_INDEX]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.rgb)
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


def to_data_url(png_bytes: bytes) -> str:
    """تحويل PNG bytes إلى data URL"""
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode()


def sha256_bytes(b: bytes) -> str:
    """حساب SHA256 hash للبيانات"""
    return hashlib.sha256(b).hexdigest()


def get_active_window_signature() -> str:
    """
    الحصول على معرّف النافذة النشطة (Windows فقط)
    يتطلب pywin32
    """
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) or ""
        return f"win:{hwnd}:{title.strip()}"
    except Exception:
        return "unknown-window"


def extract_window_title_from_signature(sig: str) -> str:
    """استخراج عنوان النافذة من المعرّف"""
    if sig.startswith("win:"):
        parts = sig.split(":", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return ""
