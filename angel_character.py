"""
شخصية الملاك - الملاك المساعد
================================
Widget PyQt6 للشخصية المتحركة
"""

import math
import random
import re
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, pyqtSignal, pyqtProperty, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QRadialGradient, QLinearGradient, QPainterPath, QFont, QTextDocument
from PyQt6.QtWidgets import QWidget, QApplication

from config import CHARACTER_SIZE_W, CHARACTER_SIZE_H, TOP_BUBBLE_AREA, COLORS
from angel_state import AngelState


def _escape_html(s: str) -> str:
    """تهريب أحرف HTML"""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _speech_markdown_to_html(text: str) -> str:
    """
    تحويل رموز التنسيق في النص إلى HTML للفقاعة:
    ***نص*** = عريض + أكبر، **نص** = عريض، *نص* = مائل، `نص` = كود، __نص__ = تسطير
    """
    if not text:
        return ""
    s = _escape_html(text)
    # ترتيب مهم: *** قبل ** قبل *
    s = re.sub(r"\*\*\*(.+?)\*\*\*", lambda m: "<b><span style='font-size:13px'>" + m.group(1) + "</span></b>", s)
    s = re.sub(r"\*\*(.+?)\*\*", lambda m: "<b>" + m.group(1) + "</b>", s)
    s = re.sub(r"\*([^*]+?)\*", lambda m: "<i>" + m.group(1) + "</i>", s)
    s = re.sub(r"__([^_]+?)__", lambda m: "<u>" + m.group(1) + "</u>", s)
    s = re.sub(r"`([^`]+)`", lambda m: "<span style='background:rgba(0,0,0,0.08);padding:1px 4px;border-radius:3px;font-family:Consolas;font-size:10px'>" + m.group(1) + "</span>", s)
    return s


def _speech_plain_for_layout(text: str) -> str:
    """إزالة رموز التنسيق للحصول على النص الخام (لحساب حجم الفقاعة)"""
    if not text:
        return ""
    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+?)\*", r"\1", s)
    s = re.sub(r"__([^_]+?)__", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s


class AngelCharacter(QWidget):
    """
    شخصية الملاك المتحركة
    """
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setFixedSize(CHARACTER_SIZE_W, CHARACTER_SIZE_H)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # ✅ إزالة Tool لإظهار التطبيق في شريط المهام
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Window  # ✅ يظهر في شريط المهام
        )
        self.setMouseTracking(True)
        
        self.state = AngelState.IDLE
        self.current_frame = 0
        self.breath_phase = 0
        self.wing_phase = 0
        self.glow_intensity = 0.55
        self.is_blinking = False
        self.eye_blink_timer = 0
        
        self.primary_color = QColor(COLORS["primary"])
        self.secondary_color = QColor(COLORS["accent"])
        
        self._rotation_angle = 0.0
        self.is_moving = False
        
        self.is_hovered = False
        self.hover_scale = 1.0
        self.hover_ring_phase = 0.0   # طور حلقة التوهج عند الـ hover
        self.hover_bounce = 0.0        # ارتداد تفاعلي عند الـ hover
        self.is_thinking = False       # انيميشن تفكير (عند طلب اقتراح)
        
        self.sparkles = []
        self.sparkle_timer = 0
        
        self.wander_timer = QTimer(self)
        self.wander_timer.timeout.connect(self._wander_around)
        self.wander_timer.start(random.randint(9000, 16000))
        
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._animate)
        self.animation_timer.start(16)
        
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self._random_blink)
        self.blink_timer.start(3200)
        
        self.speech_bubble_text = ""
        self.speech_bubble_full_text = ""  # النص الكامل
        self.speech_bubble_visible = False
        self.speech_bubble_timer = QTimer(self)
        self.speech_bubble_timer.timeout.connect(self._hide_speech_bubble)
        
        # ✅ تأثير الكتابة كلمة كلمة
        self.typing_words = []  # قائمة الكلمات
        self.typing_index = 0   # الفهرس الحالي
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self._type_next_word)
        self.is_typing = False
        
        self._pos_anim: Optional[QPropertyAnimation] = None
    
    @pyqtProperty(float)
    def rotation_angle(self):
        return self._rotation_angle
    
    @rotation_angle.setter
    def rotation_angle(self, value):
        self._rotation_angle = value
        self.update()
    
    def set_thinking(self, value: bool):
        """تفعيل/إلغاء انيميشن التفكير (عند طلب اقتراح)"""
        self.is_thinking = value
        self.update()
    
    def set_state(self, state: AngelState):
        """تغيير حالة الملاك"""
        self.state = state
        if state == AngelState.ALERT:
            self.primary_color = QColor(COLORS["alert"])
        elif state == AngelState.HELPING:
            self.primary_color = QColor(COLORS["help"])
        else:
            self.primary_color = QColor(COLORS["primary"])
        self.update()
    
    def _animate(self):
        """دورة الرسوم المتحركة"""
        self.current_frame += 1
        self.breath_phase += 0.05
        # أجنحة أسرع عند التفكير أو الحركة
        wing_speed = 0.08
        if self.is_moving:
            wing_speed = 0.15
        elif getattr(self, "is_thinking", False):
            wing_speed = 0.22
        self.wing_phase += wing_speed
        
        base = 0.55 + 0.25 * math.sin(self.current_frame * 0.05)
        if self.state == AngelState.ALERT:
            base = 0.88 + 0.12 * math.sin(self.current_frame * 0.20)
        elif self.state == AngelState.HELPING:
            base = 0.78 + 0.18 * math.sin(self.current_frame * 0.12)
        
        self.glow_intensity = base + (0.18 if self.is_hovered else 0.0)
        self.floating_offset = 5 * math.sin(self.current_frame * 0.03)
        
        # حلقة التوهج عند الـ hover
        if self.is_hovered:
            self.hover_ring_phase = min(1.0, self.hover_ring_phase + 0.06)
            self.hover_bounce = 4 * math.sin(self.current_frame * 0.2)
        else:
            self.hover_ring_phase = max(0.0, self.hover_ring_phase - 0.04)
            self.hover_bounce *= 0.9
        
        if self.is_blinking:
            self.eye_blink_timer += 1
            if self.eye_blink_timer > 8:
                self.is_blinking = False
                self.eye_blink_timer = 0
        
        if self.is_hovered:
            self.hover_scale = min(1.15, self.hover_scale + 0.02)
        else:
            self.hover_scale = max(1.0, self.hover_scale - 0.02)
        
        if self.is_moving:
            self.rotation_angle = 5 * math.sin(self.current_frame * 0.1)
        elif getattr(self, "is_thinking", False):
            # انيميشن تفكير: تمايل خفيف يمين–يسار
            self.rotation_angle = 4 * math.sin(self.current_frame * 0.18)
        else:
            self.rotation_angle *= 0.94
            # تمايل خفيف جداً في وضع السكون
            self.rotation_angle += 0.25 * math.sin(self.current_frame * 0.02)
        
        self._animate_sparkles()
        self.update()
    
    def _animate_sparkles(self):
        """تحريك الشرارات"""
        self.sparkle_timer += 1
        if getattr(self, "is_thinking", False) and self.sparkle_timer > 5:
            for _ in range(1):
                self.sparkles.append({
                    'x': random.randint(-50, 50),
                    'y': random.randint(-65, 65),
                    'life': 50,
                    'size': random.randint(3, 7),
                    'speed': random.uniform(0.6, 1.8)
                })
            self.sparkle_timer = 0
        elif self.is_hovered and self.sparkle_timer > 8:
            for _ in range(2):
                self.sparkles.append({
                    'x': random.randint(-55, 55),
                    'y': random.randint(-75, 75),
                    'life': 70,
                    'size': random.randint(4, 10),
                    'speed': random.uniform(0.8, 2.5)
                })
            self.sparkle_timer = 0
        elif self.sparkle_timer > 30 and random.random() > 0.72:
            self.sparkles.append({
                'x': random.randint(-50, 50),
                'y': random.randint(-70, 70),
                'life': 60,
                'size': random.randint(3, 8),
                'speed': random.uniform(0.5, 2.0)
            })
            self.sparkle_timer = 0
        
        for sp in self.sparkles[:]:
            sp['life'] -= 1
            sp['y'] -= sp['speed']
            sp['x'] += math.sin(sp['life'] * 0.1) * 0.5
            if sp['life'] <= 0:
                self.sparkles.remove(sp)
    
    def _wander_around(self):
        """التنقل العشوائي"""
        if self.state == AngelState.SLEEPING or self.is_moving:
            return
        
        screen = QApplication.primaryScreen().geometry()
        
        corner_positions = [
            (50, 50),
            (screen.width() - 390, 50),
            (50, screen.height() - 390),
            (screen.width() - 390, screen.height() - 390),
            (screen.width() // 2 - 160, 50),
            (screen.width() // 2 - 160, screen.height() - 390),
        ]
        
        if random.random() < 0.7:
            x, y = random.choice(corner_positions)
        else:
            x = random.randint(20, max(20, screen.width() - 390))
            y = random.randint(20, max(20, screen.height() - 390))
        
        self.move_to(x, y, animated=True)
        self.is_moving = True
        QTimer.singleShot(1200, lambda: setattr(self, "is_moving", False))
        self.wander_timer.setInterval(random.randint(9000, 16000))
    
    def _random_blink(self):
        """رمش عشوائي"""
        if random.random() > 0.3:
            self.is_blinking = True
    
    def paintEvent(self, event):
        """رسم الشخصية"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        cx = self.width() // 2
        floating = getattr(self, "floating_offset", 0) + getattr(self, "hover_bounce", 0)
        cy = int((self.height() // 2) + (TOP_BUBBLE_AREA // 2) + floating)
        
        if self.speech_bubble_visible:
            self._draw_speech_bubble(painter)
        
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.rotation_angle)
        painter.scale(self.hover_scale, self.hover_scale)
        painter.translate(-cx, -cy)
        
        self._draw_glow(painter, cx, cy)
        self._draw_hover_ring(painter, cx, cy)
        self._draw_sparkles(painter, cx, cy)
        self._draw_wings(painter, cx, cy)
        self._draw_halo(painter, cx, cy - 50)
        self._draw_body(painter, cx, cy)
        self._draw_face(painter, cx, cy - 15)
        
        painter.restore()
    
    def _draw_glow(self, painter: QPainter, cx: int, cy: int):
        """رسم التوهج"""
        gradient = QRadialGradient(cx, cy, 90)
        glow = QColor(self.primary_color)
        glow.setAlpha(int(80 * self.glow_intensity))
        gradient.setColorAt(0, glow)
        gradient.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(cx - 90, cy - 90, 180, 180)
    
    def _draw_hover_ring(self, painter: QPainter, cx: int, cy: int):
        """حلقة توهج تفاعلية عند وضع الماوس على الشخصية"""
        phase = getattr(self, "hover_ring_phase", 0)
        if phase <= 0:
            return
        # حلقة تتوسع وتتلاشى
        r = 55 + 25 * math.sin(self.current_frame * 0.15)
        alpha = int(80 * phase * (0.5 + 0.5 * math.sin(self.current_frame * 0.1)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 220, 150, alpha), 3))
        painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
        painter.setPen(QPen(QColor(255, 255, 255, alpha // 2), 2))
        painter.drawEllipse(int(cx - r - 4), int(cy - r - 4), int((r + 4) * 2), int((r + 4) * 2))
    
    def _draw_sparkles(self, painter: QPainter, cx: int, cy: int):
        """رسم الشرارات"""
        for sp in self.sparkles:
            alpha = int((sp['life'] / 60) * 255)
            color = QColor(255, 255, 150, alpha)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            x = cx + sp['x']
            y = cy + sp['y']
            s = sp['size']
            painter.drawEllipse(int(x - s/2), int(y - s/2), s, s)
            painter.setPen(QPen(color, 1))
            painter.drawLine(int(x - s), int(y), int(x + s), int(y))
            painter.drawLine(int(x), int(y - s), int(x), int(y + s))
    
    def _draw_wings(self, painter: QPainter, cx: int, cy: int):
        """رسم الأجنحة"""
        wing_angle = 18 * math.sin(self.wing_phase)
        
        painter.save()
        painter.translate(cx + 22, cy + 5)
        painter.rotate(wing_angle - 25)
        self._draw_wing_shape(painter, 1)
        painter.restore()
        
        painter.save()
        painter.translate(cx - 22, cy + 5)
        painter.rotate(-wing_angle + 25)
        painter.scale(-1, 1)
        self._draw_wing_shape(painter, 1)
        painter.restore()
    
    def _draw_wing_shape(self, painter: QPainter, scale: float):
        """رسم شكل الجناح"""
        wing_path = QPainterPath()
        wing_path.moveTo(0, 0)
        wing_path.cubicTo(25 * scale, -25 * scale, 50 * scale, -20 * scale, 70 * scale, -5 * scale)
        wing_path.cubicTo(75 * scale, 5 * scale, 70 * scale, 15 * scale, 55 * scale, 20 * scale)
        wing_path.cubicTo(35 * scale, 25 * scale, 15 * scale, 20 * scale, 0, 8)
        wing_path.closeSubpath()
        
        wing_gradient = QRadialGradient(30 * scale, 0, 50 * scale)
        wing_gradient.setColorAt(0, QColor(255, 255, 255, 230))
        wing_gradient.setColorAt(0.5, QColor(240, 240, 255, 200))
        wing_gradient.setColorAt(1, QColor(200, 210, 255, 120))
        
        painter.setBrush(QBrush(wing_gradient))
        painter.setPen(QPen(QColor(220, 220, 255, 200), 2))
        painter.drawPath(wing_path)
    
    def _draw_halo(self, painter: QPainter, cx: int, cy: int):
        """رسم الهالة"""
        painter.save()
        halo_y = cy - 80
        
        halo_gradient = QLinearGradient(cx - 30, halo_y, cx + 30, halo_y)
        halo_gradient.setColorAt(0, QColor(255, 215, 0, 180))
        halo_gradient.setColorAt(0.5, QColor(255, 255, 150, 230))
        halo_gradient.setColorAt(1, QColor(255, 215, 0, 180))
        
        painter.setPen(QPen(QBrush(halo_gradient), 3.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.translate(cx, halo_y)
        painter.rotate(5 * math.sin(self.current_frame * 0.02))
        painter.drawEllipse(-28, -6, 56, 14)
        painter.restore()
    
    def _draw_body(self, painter: QPainter, cx: int, cy: int):
        """رسم الجسم"""
        breath_scale = 1 + 0.03 * math.sin(self.breath_phase)
        
        # الرأس
        head_gradient = QRadialGradient(cx - 5, cy - 40, 42)
        head_gradient.setColorAt(0, QColor(255, 255, 255))
        head_gradient.setColorAt(0.7, QColor(245, 245, 255))
        head_gradient.setColorAt(1, QColor(225, 220, 245))
        
        painter.setBrush(QBrush(head_gradient))
        painter.setPen(QPen(QColor(200, 200, 230), 2.5))
        hs = int(38 * breath_scale)
        painter.drawEllipse(cx - hs, cy - 40 - hs, hs * 2, hs * 2)
        
        # الرقبة
        neck_gradient = QLinearGradient(cx, cy - 5, cx, cy + 8)
        neck_gradient.setColorAt(0, QColor(248, 245, 255))
        neck_gradient.setColorAt(1, QColor(240, 238, 250))
        painter.setBrush(QBrush(neck_gradient))
        painter.setPen(QPen(QColor(210, 210, 235), 1.5))
        painter.drawRoundedRect(cx - 10, cy - 5, 20, 13, 5, 5)
        
        # الثوب
        robe_path = QPainterPath()
        robe_path.moveTo(cx - 32, cy)
        robe_path.quadTo(cx - 40, cy + 25, cx - 38, cy + 52)
        robe_path.quadTo(cx - 30, cy + 70, cx - 18, cy + 75)
        robe_path.lineTo(cx + 18, cy + 75)
        robe_path.quadTo(cx + 30, cy + 70, cx + 38, cy + 52)
        robe_path.quadTo(cx + 40, cy + 25, cx + 32, cy)
        robe_path.closeSubpath()
        
        robe_gradient = QLinearGradient(cx, cy, cx, cy + 75)
        robe_gradient.setColorAt(0, self.primary_color.lighter(170))
        robe_gradient.setColorAt(0.8, self.primary_color)
        robe_gradient.setColorAt(1, self.primary_color.darker(105))
        
        painter.setBrush(QBrush(robe_gradient))
        painter.setPen(QPen(self.primary_color.darker(115), 2.5))
        painter.drawPath(robe_path)
    
    def _draw_face(self, painter: QPainter, cx: int, cy: int):
        """رسم الوجه"""
        eye_y = cy - 5
        eye_spacing = 12
        
        if self.is_blinking:
            painter.setPen(QPen(QColor(80, 80, 120), 2))
            painter.drawLine(cx - eye_spacing - 5, eye_y, cx - eye_spacing + 5, eye_y)
            painter.drawLine(cx + eye_spacing - 5, eye_y, cx + eye_spacing + 5, eye_y)
        else:
            painter.setBrush(QColor(40, 40, 80))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(cx - eye_spacing - 4, eye_y - 4, 8, 8)
            painter.drawEllipse(cx + eye_spacing - 4, eye_y - 4, 8, 8)
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(cx - eye_spacing - 1, eye_y - 3, 3, 3)
            painter.drawEllipse(cx + eye_spacing - 1, eye_y - 3, 3, 3)
        
        painter.setPen(QPen(QColor(80, 80, 120), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(cx - 8, cy + 10)
        path.quadTo(cx, cy + 15, cx + 8, cy + 10)
        painter.drawPath(path)
    
    def _draw_speech_bubble(self, painter: QPainter):
        """رسم فقاعة الكلام مع دعم التنسيق: ***عريض+كبير*** **عريض** *مائل* `كود`"""
        if not self.speech_bubble_text:
            return
        
        font = QFont("Segoe UI", 11, QFont.Weight.Bold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        plain = _speech_plain_for_layout(self.speech_bubble_text)
        
        # لف النص لأسطر متعددة (حسب النص بدون رموز)
        max_width = 280
        words = plain.split()
        lines, cur = [], []
        for w in words:
            test = " ".join(cur + [w])
            if metrics.horizontalAdvance(test) <= max_width:
                cur.append(w)
            else:
                if cur:
                    lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))
        
        padding = 18
        text_width = min(320, max([metrics.horizontalAdvance(line) for line in lines] + [0]) + padding * 2)
        line_height = metrics.height() + 6
        text_height = len(lines) * line_height + padding * 2
        text_height = min(text_height, 150)
        
        cx = self.width() // 2
        bubble_x = max(8, min(cx - text_width // 2, self.width() - text_width - 8))
        bubble_y = max(8, min(10, TOP_BUBBLE_AREA - text_height - 8))
        
        # ظل
        shadow_offset = 4
        for i in range(3):
            alpha = 30 - i * 8
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                bubble_x + shadow_offset + i,
                bubble_y + shadow_offset + i,
                text_width, text_height,
                18, 18
            )
        
        # الفقاعة
        border = QColor(self.primary_color)
        border.setAlpha(230)
        
        bubble_gradient = QLinearGradient(bubble_x, bubble_y, bubble_x, bubble_y + text_height)
        bubble_gradient.setColorAt(0, QColor(255, 255, 255, 250))
        bubble_gradient.setColorAt(1, QColor(248, 250, 255, 255))
        
        painter.setBrush(QBrush(bubble_gradient))
        painter.setPen(QPen(border, 3))
        painter.drawRoundedRect(bubble_x, bubble_y, text_width, text_height, 18, 18)
        
        # المثلث
        tri_x = cx
        tri_y = bubble_y + text_height
        triangle = QPainterPath()
        triangle.moveTo(tri_x - 12, tri_y)
        triangle.lineTo(tri_x, tri_y + 16)
        triangle.lineTo(tri_x + 12, tri_y)
        triangle.closeSubpath()
        painter.drawPath(triangle)
        
        # ✅ النص منسق (*** ** * `) مع RTL — إذا كان طويلاً نعرض الأسفل ونخفي الأعلى
        html = _speech_markdown_to_html(self.speech_bubble_text)
        doc = QTextDocument()
        doc.setDefaultFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        doc.setHtml("<div align='right' dir='rtl' style='color:#19192d'>" + html + "</div>")
        doc.setTextWidth(text_width - 2 * padding)
        doc.setDefaultTextOption(doc.defaultTextOption())
        # منطقة الرسم مع القص
        text_rect = QRectF(bubble_x + padding, bubble_y + padding, text_width - 2 * padding, text_height - 2 * padding)
        painter.save()
        painter.translate(text_rect.x(), text_rect.y())
        clip = QRectF(0, 0, text_rect.width(), text_rect.height())
        painter.setClipRect(clip)
        doc_height = doc.size().height()
        # إذا النص أطول من ارتفاع الفقاعة: انزل المحتوى ليعرض الأسفل ويُخفى ما فوق
        if doc_height > text_rect.height():
            painter.translate(0, text_rect.height() - doc_height)
        doc.drawContents(painter, QRectF(0, 0, text_rect.width(), max(doc_height, text_rect.height())))
        painter.restore()
    
    def show_speech(self, text: str, duration: int = 6500, typing_effect: bool = True):
        """
        عرض رسالة في الفقاعة مع تأثير كتابة كلمة كلمة
        
        Args:
            text: النص المراد عرضه
            duration: مدة العرض (بالميلي ثانية)
            typing_effect: تفعيل تأثير الكتابة (افتراضي: True)
        """
        if not text or not text.strip():
            return
        
        self.speech_bubble_full_text = text.strip()
        self.speech_bubble_visible = True
        
        # ✅ تأثير الكتابة كلمة كلمة
        if typing_effect:
            self.typing_words = self.speech_bubble_full_text.split()
            self.typing_index = 0
            self.is_typing = True
            self.speech_bubble_text = ""
            
            # بدء الكتابة (سرعة: كلمة كل 80-120ms)
            typing_speed = 100  # ميلي ثانية لكل كلمة
            self.typing_timer.start(typing_speed)
        else:
            # بدون تأثير - عرض مباشر
            self.speech_bubble_text = self.speech_bubble_full_text
            self.is_typing = False
        
        # حساب مدة العرض بناءً على طول النص
        if typing_effect and self.typing_words:
            typing_duration = len(self.typing_words) * 100
            total_duration = max(duration, typing_duration + 2000)  # +2 ثانية بعد الانتهاء
        else:
            total_duration = duration
        
        self.speech_bubble_timer.start(total_duration)
        self.update()
    
    def _type_next_word(self):
        """✅ كتابة الكلمة التالية (تأثير الكتابة)"""
        if self.typing_index < len(self.typing_words):
            # إضافة الكلمة التالية
            if self.speech_bubble_text:
                self.speech_bubble_text += " " + self.typing_words[self.typing_index]
            else:
                self.speech_bubble_text = self.typing_words[self.typing_index]
            
            self.typing_index += 1
            self.update()
        else:
            # انتهت الكتابة
            self.is_typing = False
            self.typing_timer.stop()
            # التأكد من عرض النص الكامل
            if self.speech_bubble_text != self.speech_bubble_full_text:
                self.speech_bubble_text = self.speech_bubble_full_text
                self.update()
    
    def _hide_speech_bubble(self):
        """إخفاء الفقاعة"""
        self.speech_bubble_visible = False
        self.speech_bubble_timer.stop()
        self.typing_timer.stop()  # ✅ إيقاف timer الكتابة
        self.is_typing = False
        self.speech_bubble_text = ""
        self.speech_bubble_full_text = ""
        self.update()
    
    def move_to(self, x: int, y: int, animated: bool = True):
        """تحريك الشخصية"""
        if animated:
            anim = QPropertyAnimation(self, b"pos")
            anim.setDuration(700)
            anim.setEndValue(QPoint(x, y))
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            anim.start()
            self._pos_anim = anim
        else:
            self.move(x, y)
    
    def enterEvent(self, event):
        """عند دخول الماوس - تأثيرات تفاعلية"""
        self.is_hovered = True
        self.set_state(AngelState.HAPPY)
        # دفعة أجنحة تفاعلية
        self.wing_phase += 2.5
        # شرارات دخول
        for _ in range(10):
            self.sparkles.append({
                'x': random.randint(-60, 60),
                'y': random.randint(-80, 80),
                'life': 50,
                'size': random.randint(4, 9),
                'speed': random.uniform(1.0, 3.0)
            })
        QTimer.singleShot(800, lambda: self.set_state(AngelState.IDLE))
    
    def leaveEvent(self, event):
        """عند خروج الماوس"""
        self.is_hovered = False
    
    def mouseDoubleClickEvent(self, event):
        """النقر المزدوج - لا يغلق التطبيق (تفاعل فقط)"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
    
    def mousePressEvent(self, event):
        """عند النقر - تفاعل بسيط (وميض شرارات)"""
        if event.button() == Qt.MouseButton.LeftButton:
            for _ in range(5):
                self.sparkles.append({
                    'x': random.randint(-45, 45),
                    'y': random.randint(-60, 60),
                    'life': 45,
                    'size': random.randint(3, 7),
                    'speed': random.uniform(0.8, 2.2)
                })
            self.clicked.emit()