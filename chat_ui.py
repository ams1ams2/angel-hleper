"""
واجهة الشات و Hotkey - الملاك المساعد
=====================================
"""

import logging
import threading
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QObject
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QWidget, QLineEdit, QPushButton, QHBoxLayout, QApplication

logger = logging.getLogger("AngelAssistant.UI")


class ChatOverlay(QWidget):
    """
    نافذة الشات المنبثقة (F12)
    """
    submitted = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        # ✅ تحسين flags للحصول على focus أفضل
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus  # إزالة هذا لضمان قبول Focus
        )
        # ✅ إزالة Tool لإظهار النافذة بشكل صحيح
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # ✅ Tool مناسب للنوافذ المنبثقة الصغيرة
        )
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(600, 75)
        
        wrap = QWidget(self)
        wrap.setStyleSheet("""
            QWidget{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,0.98), stop:1 rgba(248,250,255,0.98));
                border: 3px solid rgba(124,58,237,0.7);
                border-radius: 22px;
            }
            QLineEdit{
                border: none;
                background: rgba(255,255,255,0.7);
                padding: 14px 16px;
                font-size: 15px;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                color: #1F2937;
                border-radius: 16px;
                selection-background-color: rgba(124,58,237,0.3);
            }
            QLineEdit:focus{
                background: rgba(255,255,255,0.95);
                border: 2px solid rgba(124,58,237,0.4);
            }
            QPushButton{
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(245,158,11,1), stop:1 rgba(234,140,8,1));
                color: white;
                padding: 14px 20px;
                border-radius: 16px;
                font-weight: 700;
                font-size: 14px;
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }
            QPushButton:hover{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,170,20,1), stop:1 rgba(245,158,11,1));
            }
            QPushButton:pressed{
                background: rgba(220,130,5,1);
                padding: 15px 19px 13px 21px;
            }
        """)
        wrap.setGeometry(0, 0, 600, 75)
        
        self.input = QLineEdit()
        self.input.setPlaceholderText("✨ اكتب رسالتك هنا... (اضغط Enter للإرسال)")
        
        # ✅ الاتجاه الافتراضي RTL (للعربية)
        self.input.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.input.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # ✅ مراقبة تغيير النص لتحديد الاتجاه
        self.input.textChanged.connect(self._update_text_direction)
        
        self.btn = QPushButton("📤 إرسال")
        
        row = QHBoxLayout(wrap)
        row.setContentsMargins(16, 12, 14, 12)
        row.setSpacing(12)
        row.addWidget(self.input, 1)
        row.addWidget(self.btn, 0)
        
        self.btn.clicked.connect(self._send)
        self.input.returnPressed.connect(self._send)
        
        self.hide()
    
    def open_near(self, x: int, y: int):
        """
        ✅ فتح النافذة مع ضمان الظهور والتركيز الفوري
        """
        # ✅ التأكد من التنفيذ في main thread
        app = QApplication.instance()
        if app and app.thread() != threading.current_thread():
            # ✅ استخدام QTimer.singleShot للتنفيذ في main thread
            QTimer.singleShot(0, lambda: self._open_near_internal(x, y))
            return
        
        self._open_near_internal(x, y)
    
    def _open_near_internal(self, x: int, y: int):
        """✅ التنفيذ الفعلي (في main thread)"""
        self.move(x, y)
        self.show()
        
        # ✅ مسح أي نص سابق
        self.input.clear()
        
        # ✅ استخدام Windows API لإجبار النافذة للأمام والتركيز
        self._force_window_to_front()
        
        # ✅ انتظار قليل قبل نقل التركيز (لضمان أن النافذة نشطة فعلياً)
        QTimer.singleShot(100, self._force_focus)
        QTimer.singleShot(200, self._force_focus)
        QTimer.singleShot(300, self._force_focus)
    
    def _force_window_to_front(self):
        """✅ إجبار النافذة للأمام باستخدام Windows API - طريقة قوية"""
        try:
            import win32gui
            import win32con
            import win32process
            import ctypes
            
            hwnd = int(self.winId())
            foreground_hwnd = win32gui.GetForegroundWindow()
            
            if hwnd == foreground_hwnd:
                return  # النافذة نشطة بالفعل
            
            # ✅ الحصول على thread IDs
            foreground_thread = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
            current_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
            
            # ✅ ربط threads مؤقتاً لإجبار التركيز
            if foreground_thread != current_thread:
                ctypes.windll.user32.AttachThreadInput(foreground_thread, current_thread, True)
            
            # ✅ إجبار النافذة للأمام
            win32gui.SetForegroundWindow(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetActiveWindow(hwnd)
            
            # ✅ إلغاء ربط threads
            if foreground_thread != current_thread:
                ctypes.windll.user32.AttachThreadInput(foreground_thread, current_thread, False)
            
        except ImportError:
            # Fallback: استخدام Qt فقط
            self.raise_()
            self.activateWindow()
            self.setFocus()
        except Exception:
            # Fallback: استخدام Qt فقط
            self.raise_()
            self.activateWindow()
            self.setFocus()
    
    def _force_focus(self):
        """✅ إجبار التركيز على مربع النص - طريقة قوية جداً"""
        if not self.isVisible():
            return
        
        # ✅ التأكد من أن النافذة في المقدمة أولاً
        self._force_window_to_front()
        
        # ✅ استخدام Windows API لإجبار التركيز
        try:
            import win32gui
            import win32con
            import win32process
            import ctypes
            import time
            
            hwnd = int(self.winId())
            hwnd_input = int(self.input.winId())
            
            # ✅ الحصول على thread IDs
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd:
                foreground_thread = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
            else:
                foreground_thread = None
            
            current_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
            
            # ✅ ربط threads مؤقتاً
            if foreground_thread and foreground_thread != current_thread:
                ctypes.windll.user32.AttachThreadInput(foreground_thread, current_thread, True)
            
            # ✅ إجبار النافذة للأمام
            win32gui.SetForegroundWindow(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetActiveWindow(hwnd)
            
            # ✅ انتظار قليل
            time.sleep(0.03)
            
            # ✅ إجبار التركيز على الـ input مباشرة
            win32gui.SetFocus(hwnd_input)
            
            # ✅ إلغاء ربط threads
            if foreground_thread and foreground_thread != current_thread:
                ctypes.windll.user32.AttachThreadInput(foreground_thread, current_thread, False)
            
        except Exception:
            # Fallback: Qt فقط
            self.raise_()
            self.activateWindow()
            self.setFocus()
        
        # ✅ إجبار التركيز على مربع النص (Qt)
        self.input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.input.activateWindow()
        
        # ✅ نقل المؤشر للمكان الصحيح حسب الاتجاه
        text = self.input.text()
        if self.input.layoutDirection() == Qt.LayoutDirection.RightToLeft:
            # RTL: المؤشر في بداية النص (اليمين)
            self.input.setCursorPosition(0)
        else:
            # LTR: المؤشر في نهاية النص (اليسار)
            self.input.setCursorPosition(len(text))
        
        # ✅ التأكد من أن النافذة نشطة
        self.raise_()
        self.activateWindow()
    
    def _update_text_direction(self, text: str):
        """✅ تحديث اتجاه النص حسب اللغة"""
        if not text:
            # افتراضي: RTL للعربية
            self.input.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.input.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return
        
        # ✅ كشف اللغة: إذا كان النص يحتوي على أحرف عربية
        has_arabic = any('\u0600' <= char <= '\u06FF' for char in text)
        has_english = any(char.isascii() and char.isalpha() for char in text)
        
        # ✅ إذا كان النص عربي أو مختلط (عربي أكثر) -> RTL
        # إذا كان النص إنجليزي فقط -> LTR
        if has_arabic or (not has_english and has_arabic):
            self.input.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.input.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        else:
            self.input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            self.input.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    
    def _send(self):
        """إرسال الرسالة"""
        text = (self.input.text() or "").strip()
        if not text:
            return
        
        self.input.setText("")
        self.hide()
        self.submitted.emit(text)


# =========================
# GLOBAL HOTKEY (F12) - باستخدام keyboard library
# =========================
class HotkeySignal(QObject):
    """
    ✅ QObject لإرسال signal من thread منفصل إلى main thread
    """
    hotkey_pressed = pyqtSignal()
    
    def __init__(self):
        super().__init__()


class KeyboardHotkeyListener:
    """
    ✅ استماع لـ F11 و F12 و F9 باستخدام مكتبة keyboard
    يعمل مع لوحة عربي أو إنجليزي (مفاتيح F لا تتغير)
    """
    def __init__(self, on_f12, on_f11, on_f9, app):
        self.on_f12 = on_f12
        self.on_f11 = on_f11
        self.on_f9 = on_f9
        self.app = app
        self.listener_thread = None
        self.running = False
        
        # ✅ إنشاء QObject مع signals للتواصل مع main thread
        self.f12_signal = HotkeySignal()
        self.f12_signal.hotkey_pressed.connect(self._call_f12_safe)
        
        self.f11_signal = HotkeySignal()
        self.f11_signal.hotkey_pressed.connect(self._call_f11_safe)
        
        self.f9_signal = HotkeySignal()
        self.f9_signal.hotkey_pressed.connect(self._call_f9_safe)
    
    def _call_f12_safe(self):
        """✅ استدعاء آمن في main thread"""
        try:
            self.on_f12()
        except Exception as e:
            logger.warning("⚠️ خطأ في استدعاء F12: %s", e)
    
    def _call_f11_safe(self):
        """✅ استدعاء آمن في main thread"""
        try:
            self.on_f11()
        except Exception as e:
            logger.warning("⚠️ خطأ في استدعاء F11: %s", e)
    
    def _call_f9_safe(self):
        """✅ استدعاء آمن في main thread"""
        try:
            self.on_f9()
        except Exception as e:
            logger.warning("⚠️ خطأ في استدعاء F9: %s", e)
    
    def start(self):
        """بدء الاستماع للاختصارات"""
        try:
            import keyboard
            
            def on_f12():
                """عند الضغط على F12 - يُستدعى من keyboard thread"""
                if self.running:
                    self.f12_signal.hotkey_pressed.emit()
            
            def on_f11():
                """عند الضغط على F11 - يُستدعى من keyboard thread"""
                if self.running:
                    self.f11_signal.hotkey_pressed.emit()
            
            def on_f9():
                """عند الضغط على F9 - يُستدعى من keyboard thread (عربي/إنجليزي)"""
                if self.running:
                    self.f9_signal.hotkey_pressed.emit()
            
            # ✅ تسجيل F12 و F11 و F9 (مفاتيح F تعمل بنفس الطريقة عربي/إنجليزي)
            keyboard.add_hotkey('f12', on_f12, suppress=False)
            keyboard.add_hotkey('f11', on_f11, suppress=False)
            keyboard.add_hotkey('f9', on_f9, suppress=False)
            # ✅ Alt+F9 كبديل إضافي
            try:
                keyboard.add_hotkey('alt+f9', on_f9, suppress=False)
            except Exception:
                pass
            
            self.running = True
            logger.info("✅ تم تفعيل F11 و F12 و F9 عالميًا (keyboard library)")
            return True
        
        except ImportError:
            logger.warning("⚠️ مكتبة keyboard غير مثبتة")
            logger.warning("⚠️ قم بتشغيل: pip install keyboard")
            return False
        except Exception as e:
            logger.warning("⚠️ تعذر تفعيل الاختصارات: %s", e)
            return False
    
    def stop(self):
        """إيقاف الاستماع"""
        self.running = False
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass


def try_register_global_f12():
    """
    ✅ تسجيل F12 باستخدام keyboard library (طريقة بديلة موثوقة)
    """
    try:
        import keyboard
        # فقط التحقق من أن المكتبة متاحة
        return True
    except ImportError:
        logger.warning("⚠️ مكتبة keyboard غير مثبتة")
        logger.warning("⚠️ قم بتشغيل: pip install keyboard")
        return False
    except Exception as e:
        logger.warning("⚠️ خطأ في keyboard: %s", e)
        return False


def try_unregister_global_f12():
    """إلغاء تسجيل F12"""
    try:
        import keyboard
        keyboard.unhook_all()
    except Exception:
        pass
