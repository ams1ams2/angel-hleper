"""
الملاك المساعد v2 - الملف الرئيسي
===================================
✅ تم تقسيم الكود إلى modules منفصلة
✅ إصلاح مشكلة التجميد عند إرسال من الواجهة
✅ إصلاح F12 للعمل مباشرة بدون الضغط على الشخصية
✅ إضافة نافذة إعدادات API key (F9 أو Alt+F9)

للتشغيل:
python main.py
"""

import logging
import os
import random
import sys
from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon


def resource_path(relative_path: str) -> str:
    """مسار الملف يعمل داخل exe (PyInstaller) وخارج exe"""
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# Imports من الـ modules
from config import COLORS, reload_api_key
from angel_character import AngelCharacter
from angel_state import AngelState, classify_state_from_text
from chat_ui import ChatOverlay, KeyboardHotkeyListener, try_register_global_f12, try_unregister_global_f12
from workers import VisualSuggestionWorker, ChatWorker
from settings_window import SettingsWindow

# =====================================
# LOGGING
# =====================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AngelAssistant.Main")


# =====================================
# MAIN APPLICATION
# =====================================
def main():
    """
    نقطة دخول التطبيق الرئيسية
    """
    logger.info("🚀 بدء تشغيل الملاك المساعد v2")
    
    # ✅ Windows: حتى تظهر أيقونة التطبيق على زر شريط المهام وليس أيقونة Python
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AngelAssistant.Malak.2")
        except Exception as e:
            logger.warning("⚠️ تعيين AppUserModelID: %s", e)
    
    app = QApplication(sys.argv)
    
    # ✅ إعداد اسم التطبيق
    app.setApplicationName("الملاك المساعد")
    app.setApplicationDisplayName("الملاك المساعد v2")
    
    # ✅ تعيين أيقونة التطبيق بالكامل (النافذة + شريط المهام) — مصدرها الكود وليس --icon في PyInstaller
    icon_path = resource_path("app.ico")
    app_icon = None
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    else:
        logger.warning("⚠️ ملف الأيقونة غير موجود: %s", icon_path)
    
    # ===== إنشاء النافذة الرئيسية (الشخصية) =====
    angel = AngelCharacter()
    angel.setWindowTitle("الملاك المساعد")
    if app_icon:
        angel.setWindowIcon(app_icon)  # أيقونة النافذة الرئيسية = شريط المهام
    
    # ✅ النقر المزدوج على الشخصية = طلب اقتراح فوراً
    def on_double_click_angel():
        """النقر المزدوج: توليد اقتراح فوراً مع انيميشن تفكير"""
        vis_worker.request_suggestion_now()
        angel.set_thinking(True)
        angel.set_state(AngelState.HELPING)
        angel.show_speech("جاري توليد اقتراح... 💡", duration=15000)
    
    angel.double_clicked.connect(on_double_click_angel)
    angel.show()
    
    # ✅ Windows: فرض أيقونة النافذة عبر Win32 API (احتياطي إن لم تكفِ setWindowIcon)
    def _apply_taskbar_icon_win32():
        if sys.platform != "win32" or not icon_path or not os.path.exists(icon_path):
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            WM_SETICON = 0x0080
            ICON_SMALL, ICON_BIG = 0, 1
            hwnd = int(angel.winId())
            path_abs = os.path.abspath(icon_path)
            hicon = user32.LoadImageW(None, path_abs, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
            if hicon:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
                logger.info("✅ أيقونة شريط المهام مضبوطة عبر Win32 (app.ico)")
            else:
                logger.warning("⚠️ LoadImageW لم ينجح - تأكد أن app.ico بصيغة ICO صحيحة (Windows Icon)")
        except Exception as e:
            logger.warning("⚠️ تعيين أيقونة Win32: %s", e)
    
    if sys.platform == "win32" and icon_path:
        app.processEvents()
        _apply_taskbar_icon_win32()
        QTimer.singleShot(200, _apply_taskbar_icon_win32)  # إعادة المحاولة بعد ظهور زر الشريط
    
    screen = QApplication.primaryScreen().geometry()
    angel.move(screen.width() - 390, screen.height() - 390)
    
    # ===== إنشاء واجهة الشات =====
    chat = ChatOverlay()
    
    # ===== إنشاء نافذة الإعدادات =====
    settings_window = SettingsWindow()
    if app_icon:
        settings_window.setWindowIcon(app_icon)
    
    # ===== أيقونة الشريط الأسفل (منطقة الإشعارات بجانب الساعة) =====
    tray_icon = None
    if app_icon and QSystemTrayIcon.isSystemTrayAvailable():
        tray_icon = QSystemTrayIcon()
        tray_icon.setIcon(app_icon)
        tray_icon.setToolTip("الملاك المساعد v2")
        tray_icon.setVisible(True)
        logger.info("✅ أيقونة الشريط (System Tray) مفعّلة - app.ico")
    
    # =====================================
    # API KEY CHECK & NOTIFICATIONS
    # =====================================
    def check_and_notify_api_key():
        """التحقق من وجود API key وإظهار إشعارات مزعجة"""
        from config import OPENROUTER_API_KEY
        current_key = reload_api_key()
        
        if not current_key:
            # ✅ إشعار من الشخصية
            angel.set_state(AngelState.ALERT)
            angel.show_speech(
                "⚠️ مفتاح API مطلوب! اضغط F9 لإدخاله 🔑",
                duration=6000
            )
            
            # ✅ نافذة إشعار مزعجة
            from PyQt6.QtWidgets import QMessageBox
            from PyQt6.QtCore import Qt
            msg = QMessageBox()
            msg.setWindowTitle("🔑 مفتاح API مطلوب - الملاك المساعد")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText("⚠️ مفتاح API غير موجود!")
            msg.setInformativeText(
                "الملاك المساعد يحتاج إلى مفتاح API من OpenRouter للعمل.\n\n"
                "📝 الخطوات:\n"
                "1️⃣ اذهب إلى: https://openrouter.ai/keys\n"
                "2️⃣ سجل دخول أو أنشئ حساب مجاني\n"
                "3️⃣ أنشئ مفتاح API جديد (مجاني)\n"
                "4️⃣ اضغط F9 لفتح الإعدادات\n"
                "5️⃣ أدخل المفتاح واضغط 'حفظ المفتاح'\n\n"
                "💡 يمكنك الضغط على الزر أدناه لفتح الإعدادات الآن!"
            )
            
            # ✅ زر مخصص لفتح الإعدادات
            open_btn = msg.addButton("⚙️ فتح الإعدادات (F9)", QMessageBox.ButtonRole.AcceptRole)
            close_btn = msg.addButton("❌ إغلاق", QMessageBox.ButtonRole.RejectRole)
            
            # ✅ جعل النافذة مزعجة (تظهر في المقدمة)
            msg.setWindowFlags(
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.WindowCloseButtonHint |
                Qt.WindowType.Dialog
            )
            
            result = msg.exec()
            
            # ✅ فتح الإعدادات عند الضغط على الزر الأول
            clicked_btn = msg.clickedButton()
            if clicked_btn == open_btn:
                # فتح الإعدادات
                settings_window.show()
                settings_window.raise_()
                settings_window.activateWindow()
                QTimer.singleShot(100, lambda: settings_window.api_key_input.setFocus())
            
            # إعادة الحالة بعد 3 ثواني
            QTimer.singleShot(3000, lambda: angel.set_state(AngelState.IDLE))
            return False
        return True
    
    # ✅ التحقق عند بدء التشغيل
    api_key_exists = check_and_notify_api_key()
    
    # ✅ إشعار دوري كل دقيقة إذا لم يكن API key موجوداً
    api_key_check_timer = QTimer()
    if not api_key_exists:
        def periodic_api_key_check():
            """فحص دوري كل دقيقة"""
            if not check_and_notify_api_key():
                # استمرار الإشعارات
                pass
        
        api_key_check_timer.timeout.connect(periodic_api_key_check)
        api_key_check_timer.start(60000)  # كل دقيقة
    else:
        api_key_check_timer.stop()
    
    # ===== إنشاء Visual Worker Thread =====
    vis_worker = VisualSuggestionWorker()
    vis_thread = QThread()
    vis_worker.moveToThread(vis_thread)
    
    # ===== إنشاء Chat Worker (يعمل في نفس thread مع VisualWorker) =====
    # ✅ بدون thread منفصل - يعمل مباشرة مع الأوامر الأساسية
    chat_worker = ChatWorker(vis_worker.mem)
    
    # =====================================
    # HOTKEY HANDLERS
    # =====================================
    def toggle_chat_box():
        """
        ✅ فتح/إخفاء نافذة الشات (Toggle)
        يعمل مباشرة عند الضغط على F12 من أي نافذة
        """
        if chat.isVisible():
            # ✅ إخفاء الواجهة
            chat.hide()
            angel.set_state(AngelState.IDLE)
        else:
            # ✅ فتح الواجهة
            # حساب موقع الشات بالنسبة للملاك
            ax = angel.x()
            ay = angel.y()
            chat_x = max(20, ax - 200)
            chat_y = max(20, ay - 80)
            
            # ✅ فتح الشات مع تركيز محسّن
            chat.open_near(chat_x, chat_y)
            
            # تحديث حالة الملاك
            angel.set_state(AngelState.TALKING)
            angel.show_speech("اكتب رسالتك ✍️ واضغط Enter 😄", duration=2200)
            QTimer.singleShot(1400, lambda: angel.set_state(AngelState.IDLE))
    
    def move_angel_random():
        """
        ✅ تحريك الشخصية لموقع عشوائي (F11)
        """
        screen = QApplication.primaryScreen().geometry()
        
        # مواقع عشوائية
        x = random.randint(50, screen.width() - 370)
        y = random.randint(50, screen.height() - 370)
        
        angel.move_to(x, y, animated=True)
        angel.set_state(AngelState.HAPPY)
        angel.show_speech("انتقلت! 🚀", duration=1500)
        QTimer.singleShot(1000, lambda: angel.set_state(AngelState.IDLE))
    
    def open_settings():
        """
        ✅ فتح نافذة الإعدادات (F9 أو Alt+F9 - يعمل عربي/إنجليزي)
        """
        if settings_window.isVisible():
            settings_window.hide()
        else:
            settings_window.show()
            settings_window.raise_()
            settings_window.activateWindow()
    
    # ===== معالج تحديث API key =====
    def on_api_key_updated(new_key: str):
        """عند تحديث API key - إعادة تحميله"""
        reload_api_key()
        logger.info("✅ تم تحديث API key")
        angel.set_state(AngelState.HAPPY)
        angel.show_speech("تم حفظ الإعدادات! ✨", duration=2000)
        QTimer.singleShot(1500, lambda: angel.set_state(AngelState.IDLE))
    
    settings_window.api_key_updated.connect(on_api_key_updated)
    
    # ===== تسجيل F11 و F12 و F9 العالمي باستخدام keyboard library =====
    global_ok = try_register_global_f12()
    keyboard_listener = None
    
    if global_ok:
        try:
            # ✅ F9 يفتح الإعدادات (نفس طريقة F11/F12 - يعمل عربي أو إنجليزي)
            keyboard_listener = KeyboardHotkeyListener(toggle_chat_box, move_angel_random, open_settings, app)
            if keyboard_listener.start():
                logger.info("✅ F11 و F12 و F9 العالمي مفعّل - يعمل من أي نافذة (keyboard library)")
            else:
                global_ok = False
                keyboard_listener = None
        except Exception as e:
            logger.warning("⚠️ خطأ في تفعيل keyboard listener: %s", e)
            global_ok = False
            keyboard_listener = None
    
    if not global_ok:
        # fallback: داخل التطبيق فقط
        from PyQt6.QtGui import QKeySequence, QShortcut
        sc_f12 = QShortcut(QKeySequence("F12"), angel)
        sc_f12.activated.connect(toggle_chat_box)
        sc_f11 = QShortcut(QKeySequence("F11"), angel)
        sc_f11.activated.connect(move_angel_random)
        sc_f9 = QShortcut(QKeySequence("F9"), angel)
        sc_f9.activated.connect(open_settings)
        logger.info("ℹ️ F11 و F12 و F9 يعمل داخل التطبيق فقط (fallback)")
    
    # =====================================
    # VISUAL SUGGESTIONS HANDLER
    # =====================================
    def on_suggestion(text: str):
        """
        معالج الاقتراحات البصرية
        يُستدعى عند وصول اقتراح جديد
        """
        angel.set_thinking(False)
        state = classify_state_from_text(text)
        angel.set_state(state)
        angel.show_speech(text, duration=5200)
        
        # إضافة تأثيرات بصرية حسب الحالة
        if state == AngelState.ALERT:
            for _ in range(12):
                angel.sparkles.append({
                    'x': random.randint(-55, 55),
                    'y': random.randint(-70, 20),
                    'life': 60,
                    'size': random.randint(5, 12),
                    'speed': random.uniform(1.2, 3.4)
                })
        elif state == AngelState.HELPING:
            for _ in range(8):
                angel.sparkles.append({
                    'x': random.randint(-45, 45),
                    'y': random.randint(-60, 30),
                    'life': 55,
                    'size': random.randint(4, 10),
                    'speed': random.uniform(1.0, 2.8)
                })
        
        QTimer.singleShot(2200, lambda: angel.set_state(AngelState.IDLE))
    
    vis_worker.suggestion_ready.connect(on_suggestion)
    vis_thread.started.connect(vis_worker.run)
    vis_thread.start()
    
    # =====================================
    # CHAT HANDLERS
    # =====================================
    def on_chat_submit(user_text: str):
        """
        ✅ معالج إرسال الرسالة - يعمل مباشرة مع الأوامر الأساسية
        بدون QThread منفصل - بدون query بينهم
        """
        angel.set_state(AngelState.HELPING)
        angel.show_speech("تمام.. لحظة وبرد عليك 🤝✨", duration=2200)
        
        # ✅ استدعاء مباشر - يعمل في background thread عادي
        # بدون query أو تنسيق - تنفيذ مباشر مع الأوامر الأساسية
        chat_worker.handle_chat(user_text)
    
    chat.submitted.connect(on_chat_submit)
    
    def on_chat_reply(reply: str):
        """
        معالج استلام الرد من الـ API
        """
        st = classify_state_from_text(reply)
        angel.set_state(st)
        angel.show_speech(reply, duration=8200)
        QTimer.singleShot(2600, lambda: angel.set_state(AngelState.IDLE))
    
    chat_worker.reply_ready.connect(on_chat_reply)
    
    # =====================================
    # CLEANUP
    # =====================================
    def cleanup():
        """تنظيف الموارد عند الإغلاق"""
        logger.info("🔴 إيقاف التطبيق...")
        
        try:
            vis_worker.stop()
            vis_thread.quit()
            vis_thread.wait(1200)
        except Exception as e:
            logger.warning("⚠️ خطأ في إيقاف vis_thread: %s", e)
        
        # ✅ لا حاجة لإيقاف chat_thread - يعمل في نفس thread
        
        try:
            if global_ok and keyboard_listener:
                keyboard_listener.stop()
                try_unregister_global_f12()
        except Exception as e:
            logger.warning("⚠️ خطأ في إلغاء تسجيل F12: %s", e)
        
        logger.info("✅ تم إيقاف التطبيق بنجاح")
    
    app.aboutToQuit.connect(cleanup)
    
    # ===== رسالة بدء التشغيل =====
    if api_key_exists:
        angel.set_state(AngelState.HELPING)
        angel.show_speech(
            "جاهز 😄 غيّر نافذة أو نقرتين على الشخصية لاقتراح فوري.. وF12 للشات ✨ وF9 للإعدادات",
            duration=5200
        )
        QTimer.singleShot(2200, lambda: angel.set_state(AngelState.IDLE))
    else:
        # إذا لم يكن API key موجوداً، الرسالة ستكون من الإشعار
        pass
    
    logger.info("✅ التطبيق يعمل بنجاح - اضغط F12 من أي مكان! وF9 للإعدادات")
    
    # ===== تشغيل التطبيق =====
    app.exec()


if __name__ == "__main__":
    main()
