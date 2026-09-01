@echo off
setlocal EnableExtensions
title Applio RDNA4 卸载

rem ENCODING: final uninstall.bat is ANSI/GBK. Edit builder/uninstall.tpl.bat
rem and rebuild. No chcp 65001 (cmd line-reader desync bug with multibyte).

set "INSTDIR=C:\Applio-RDNA4"
if not exist "%INSTDIR%\Applio\app.py" set "INSTDIR=%LOCALAPPDATA%\Programs\Applio-RDNA4"
if not exist "%INSTDIR%\Applio\app.py" goto not_found
echo 即将删除:
echo   %INSTDIR%
echo   %INSTDIR%-cache
echo   桌面快捷方式 Applio 推理 / Applio 训练
echo.
echo   注意: 训练产物 logs 目录也在安装目录内, 有需要请先备份!
echo.
echo   确认删除请按 Y, 退出请按 N, 60 秒后自动退出
choice /c YN /n /t 60 /d N >nul
if errorlevel 2 goto canceled
powershell -NoProfile -EncodedCommand {{BLOB_LNKDEL}} >nul 2>nul
rd /s /q "%INSTDIR%"
rd /s /q "%INSTDIR%-cache"
if exist "%INSTDIR%" goto del_fail
echo 卸载完成
pause
exit /b 0

:not_found
echo 未找到已安装的 Applio RDNA4
echo 检查过: C:\Applio-RDNA4 和 %LOCALAPPDATA%\Programs\Applio-RDNA4
echo 如安装在自定义位置, 直接删除该文件夹即可完全卸载
pause
exit /b 0

:canceled
echo 已取消, 未做任何修改
pause
exit /b 0

:del_fail
echo [提示] 部分文件未能删除, 请关闭正在运行的 Applio 后重试
pause
exit /b 1
