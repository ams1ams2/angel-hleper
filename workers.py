"""
Workers - معالجة المهام في Threads منفصلة
==========================================
"""

import time
import random
import threading
import logging
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal

from config import (
    CAPTURE_EVERY_SECONDS, POLL_EVERY_SECONDS,
    MIN_SECONDS_BETWEEN_CAPTURES, MAX_HISTORY,
    FALLBACK_SUGGESTIONS
)
from utils import (
    capture_screen_png, to_data_url, sha256_bytes,
    get_active_window_signature, extract_window_title_from_signature
)
from memory import (
    load_memory, save_memory,
    update_profile_from_window, remember_topic
)
from api_client import ask_openrouter_vision, ask_openrouter_chat
from text_utils import normalize_one_sentence_ar, normalize_chat_ar, is_good_suggestion, _clean_weird_quotes

logger = logging.getLogger("AngelAssistant.Workers")


def should_capture(now: float, last_capture_ts: float, window_sig: str, last_window_sig: str) -> bool:
    """تحديد ما إذا كان يجب التقاط الشاشة"""
    time_due = (now - last_capture_ts) >= CAPTURE_EVERY_SECONDS
    window_changed = (window_sig != last_window_sig) and (window_sig != "unknown-window")
    return time_due or window_changed


class VisualSuggestionWorker(QObject):
    """
    Worker لمعالجة الاقتراحات البصرية في thread منفصل
    """
    suggestion_ready = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._stop = False
        self._request_suggestion = threading.Event()
        self.mem = load_memory()
        self.last_capture_ts = 0.0
        self.last_window_sig = ""
        self.last_image_hash = ""
        self.last_capture_hard_gate = 0.0
    
    def request_suggestion_now(self):
        """طلب توليد اقتراح فوراً (مثلاً عند النقر المزدوج على الشخصية)"""
        self._request_suggestion.set()
    
    def stop(self):
        """إيقاف الـ Worker"""
        self._stop = True
    
    def run(self):
        """الحلقة الرئيسية للـ Worker"""
        logger.info("🧠 Visual Worker بدأ (OpenRouter)")
        
        while not self._stop:
            now = time.time()
            
            window_sig = get_active_window_signature()
            window_title = extract_window_title_from_signature(window_sig)
            
            manual_request = self._request_suggestion.is_set()
            if manual_request:
                self._request_suggestion.clear()
            
            trigger = should_capture(now, self.last_capture_ts, window_sig, self.last_window_sig) or manual_request
            
            if trigger and not manual_request and (now - self.last_capture_hard_gate) < MIN_SECONDS_BETWEEN_CAPTURES:
                trigger = False
            
            if trigger:
                try:
                    png = capture_screen_png()
                    img_hash = sha256_bytes(png)
                    
                    if window_sig == "unknown-window":
                        if img_hash == self.last_image_hash and (now - self.last_capture_ts) < CAPTURE_EVERY_SECONDS:
                            trigger = False
                    
                    if trigger:
                        update_profile_from_window(self.mem, window_title)
                        
                        suggestion = ask_openrouter_vision(to_data_url(png), self.mem, max_tries=3)
                        suggestion = normalize_one_sentence_ar(suggestion)
                        
                        if not is_good_suggestion(suggestion):
                            suggestion = random.choice(FALLBACK_SUGGESTIONS)
                        
                        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        logger.info("💡 [%s] %s", ts_str, suggestion)
                        
                        self.mem["last_suggestion"] = suggestion
                        remember_topic(self.mem, suggestion)
                        
                        self.mem.setdefault("history", []).append({
                            "ts": ts_str,
                            "window_sig": window_sig,
                            "window_title": window_title,
                            "image_hash": img_hash,
                            "suggestion": suggestion
                        })
                        
                        if len(self.mem["history"]) > MAX_HISTORY:
                            self.mem["history"] = self.mem["history"][-MAX_HISTORY:]
                        
                        save_memory(self.mem)
                        
                        self.last_capture_ts = now
                        self.last_capture_hard_gate = now
                        self.last_window_sig = window_sig
                        self.last_image_hash = img_hash
                        
                        # ✅ إرسال signal عبر Qt (thread-safe)
                        self.suggestion_ready.emit(suggestion)
                
                except Exception as e:
                    logger.warning("⚠️ خطأ في Visual Worker: %s", e)
                    time.sleep(1.2)
            
            if window_sig != "unknown-window":
                self.last_window_sig = window_sig
            
            self._request_suggestion.wait(timeout=POLL_EVERY_SECONDS)


class ChatWorker(QObject):
    """
    Worker لمعالجة المحادثات - يعمل مباشرة مع الأوامر الأساسية
    بدون thread منفصل - بدون query بينهم
    """
    reply_ready = pyqtSignal(str)
    
    def __init__(self, shared_mem: dict):
        super().__init__()
        self.mem = shared_mem
    
    def handle_chat(self, user_text: str):
        """
        ✅ معالجة المحادثة مباشرة - بدون query
        يعمل في background thread عادي (ليس QThread)
        """
        def _process_in_background():
            """تنفيذ API في background thread عادي"""
            try:
                user_text_clean = _clean_weird_quotes((user_text or "").strip())
                if not user_text_clean:
                    return
                
                # سجل المحادثة
                self.mem.setdefault("chat_history", []).append({"role": "user", "content": user_text_clean})
                self.mem["chat_history"] = self.mem["chat_history"][-16:]
                
                # ✅ استدعاء API مباشرة (في background thread - بدون query)
                reply = ask_openrouter_chat(user_text_clean, self.mem, max_tries=2)
                reply = normalize_chat_ar(reply)
                
                self.mem.setdefault("chat_history", []).append({"role": "assistant", "content": reply})
                self.mem["chat_history"] = self.mem["chat_history"][-16:]
                save_memory(self.mem)
                
                # ✅ إرسال النتيجة عبر signal (thread-safe)
                self.reply_ready.emit(reply)
            
            except Exception as e:
                logger.warning("⚠️ خطأ في ChatWorker: %s", e)
                self.reply_ready.emit("صار خطأ بسيط 😅 جرّب ترسلها مرة ثانية.")
        
        # ✅ تشغيل في background thread عادي - بدون query
        thread = threading.Thread(target=_process_in_background, daemon=True)
        thread.start()
