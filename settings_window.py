"""
نافذة الإعدادات - الملاك المساعد
==================================
نافذة بسيطة لإدخال وتعديل API key
"""

import os
import logging
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox
)

from config import COLORS

logger = logging.getLogger("AngelAssistant.Settings")


def load_api_key_from_env() -> str:
    """قراءة API key من ملف .env"""
    env_path = ".env"
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENROUTER_API_KEY=") and not line.startswith("#"):
                        return line.split("=", 1)[1].strip()
        except Exception as e:
            logger.warning("⚠️ خطأ في قراءة .env: %s", e)
    return ""


def save_api_key_to_env(api_key: str) -> bool:
    """حفظ API key في ملف .env"""
    env_path = ".env"
    try:
        # قراءة الملف الحالي إن وجد
        lines = []
        key_found = False
        
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        
        # البحث عن السطر الموجود وتحديثه
        new_lines = []
        for line in lines:
            if line.strip().startswith("OPENROUTER_API_KEY=") and not line.strip().startswith("#"):
                new_lines.append(f"OPENROUTER_API_KEY={api_key}\n")
                key_found = True
            else:
                new_lines.append(line)
        
        # إذا لم يوجد، إضافته
        if not key_found:
            new_lines.append(f"OPENROUTER_API_KEY={api_key}\n")
        
        # كتابة الملف
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        
        return True
    except Exception as e:
        logger.error("❌ خطأ في حفظ .env: %s", e)
        return False


class SettingsWindow(QWidget):
    """
    نافذة الإعدادات البسيطة
    """
    api_key_updated = pyqtSignal(str)  # Signal عند تحديث API key
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ إعدادات الملاك المساعد")
        self.setFixedSize(550, 280)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        # التصميم المحسّن
        self.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,1), stop:1 rgba(248,250,255,1));
            }}
            QLabel {{
                color: #1F2937;
                font-size: 13px;
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }}
            QLineEdit {{
                border: 2px solid rgba(124,58,237,0.4);
                background: rgba(255,255,255,1);
                padding: 12px 16px;
                font-size: 13px;
                font-family: 'Consolas', 'Courier New', monospace;
                color: #1F2937;
                border-radius: 10px;
            }}
            QLineEdit:focus {{
                border: 3px solid {COLORS['primary']};
                background: rgba(255,255,255,1);
            }}
            QPushButton {{
                border: none;
                border-radius: 10px;
                font-weight: 700;
                font-size: 14px;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                padding: 12px 24px;
                min-height: 20px;
            }}
        """)
        
        # التخطيط
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        
        # العنوان
        title = QLabel("🔑 إعدادات API Key")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {COLORS['primary']}; margin-bottom: 4px;")
        layout.addWidget(title)
        
        # التوجيهات
        info = QLabel("أدخل مفتاح API الخاص بك من OpenRouter")
        info.setStyleSheet("color: #6B7280; font-size: 13px; margin-bottom: 8px;")
        layout.addWidget(info)
        
        # حقل الإدخال مع زر الإظهار بجانبه
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-or-v1-...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setText(load_api_key_from_env())
        input_layout.addWidget(self.api_key_input, 1)
        
        # زر إظهار/إخفاء API key - محسّن
        self.toggle_btn = QPushButton("👁️")
        self.toggle_btn.setFixedWidth(50)
        self.toggle_btn.setToolTip("إظهار/إخفاء المفتاح")
        self.toggle_btn.clicked.connect(self.toggle_visibility)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(243,244,246,1), stop:1 rgba(229,231,235,1));
                color: #6B7280;
                font-size: 16px;
                padding: 10px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(229,231,235,1), stop:1 rgba(209,213,219,1));
            }}
            QPushButton:pressed {{
                background: rgba(209,213,219,1);
            }}
        """)
        input_layout.addWidget(self.toggle_btn)
        
        layout.addLayout(input_layout)
        
        # أزرار الإجراءات - محسّنة وواضحة
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        # زر حفظ - كبير وواضح
        self.save_btn = QPushButton("💾 حفظ المفتاح")
        self.save_btn.clicked.connect(self.on_save)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['primary']}, stop:1 #6D28D9);
                color: white;
                font-weight: 700;
                font-size: 14px;
                padding: 14px 28px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #8B5CF6, stop:1 {COLORS['primary']});
            }}
            QPushButton:pressed {{
                background: #6D28D9;
                padding: 15px 27px 13px 29px;
            }}
        """)
        btn_layout.addWidget(self.save_btn, 1)
        
        # زر إلغاء - واضح
        self.cancel_btn = QPushButton("❌ إلغاء")
        self.cancel_btn.clicked.connect(self.close)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(229,231,235,1), stop:1 rgba(209,213,219,1));
                color: #374151;
                font-weight: 600;
                font-size: 14px;
                padding: 14px 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(209,213,219,1), stop:1 rgba(156,163,175,1));
            }
            QPushButton:pressed {
                background: rgba(156,163,175,1);
                padding: 15px 23px 13px 25px;
            }
        """)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        
        # رابط OpenRouter - محسّن
        help_layout = QHBoxLayout()
        help_text = QLabel("💡 احصل على المفتاح من:")
        help_text.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        help_layout.addWidget(help_text)
        
        link_label = QLabel('<a href="https://openrouter.ai/keys" style="color: #7C3AED; text-decoration: none; font-weight: 600;">https://openrouter.ai/keys</a>')
        link_label.setOpenExternalLinks(True)
        link_label.setStyleSheet("color: #7C3AED; font-size: 12px; font-weight: 600;")
        help_layout.addWidget(link_label)
        help_layout.addStretch()
        
        layout.addLayout(help_layout)
    
    def toggle_visibility(self):
        """تبديل إظهار/إخفاء API key"""
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setText("🙈")
            self.toggle_btn.setToolTip("إخفاء المفتاح")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setText("👁️")
            self.toggle_btn.setToolTip("إظهار المفتاح")
    
    def on_save(self):
        """حفظ API key"""
        api_key = self.api_key_input.text().strip()
        
        if not api_key:
            QMessageBox.warning(
                self, 
                "⚠️ تحذير", 
                "يرجى إدخال API key قبل الحفظ."
            )
            return
        
        if not api_key.startswith("sk-or-v1-"):
            reply = QMessageBox.question(
                self,
                "⚠️ تأكيد",
                "API key لا يبدو صحيحاً. هل تريد المتابعة؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        if save_api_key_to_env(api_key):
            QMessageBox.information(
                self,
                "✅ تم الحفظ بنجاح",
                "تم حفظ API key بنجاح!\n\n✅ سيتم تطبيق التغييرات فوراً.\n✅ يمكنك الآن استخدام جميع الميزات."
            )
            self.api_key_updated.emit(api_key)
            self.close()
        else:
            QMessageBox.critical(
                self,
                "❌ خطأ في الحفظ",
                "فشل حفظ API key.\n\nيرجى التحقق من:\n• صلاحيات الكتابة على الملف\n• وجود مساحة كافية\n• إغلاق أي برامج تستخدم الملف"
            )
    
    def showEvent(self, event):
        """عند إظهار النافذة - تحديث API key من الملف"""
        super().showEvent(event)
        current_key = load_api_key_from_env()
        self.api_key_input.setText(current_key)
        self.api_key_input.setFocus()
