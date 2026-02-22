@echo off
chcp 65001 >nul
cls

echo =====================================
echo    🌟 الملاك المساعد v2 🌟
echo =====================================
echo.

REM التحقق من وجود Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python غير مثبت!
    echo يرجى تثبيت Python 3.8 أو أحدث
    pause
    exit /b 1
)

REM التحقق من وجود المكتبات
echo 🔍 فحص المتطلبات...
python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  المكتبات غير مثبتة!
    echo.
    echo جاري التثبيت...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ فشل التثبيت!
        pause
        exit /b 1
    )
)

echo ✅ جميع المتطلبات جاهزة!
echo.
echo 🚀 جاري تشغيل الملاك المساعد...
echo.
echo 💡 الاختصارات:
echo    F12    - فتح/إغلاق الشات
echo    F11    - تحريك الشخصية
echo    F9 - فتح الإعدادات
echo.
echo =====================================
echo.

REM تشغيل البرنامج
python main.py

REM إذا توقف البرنامج
echo.
echo =====================================
echo البرنامج توقف
echo =====================================
echo.
pause
