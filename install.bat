@echo off
setlocal EnableExtensions
title Applio ROCm RDNA4 一键安装器

rem ==================================================================
rem  Applio ROCm RDNA4 - one-click installer
rem  GPU  : AMD RX 9000 series (gfx1201 / RDNA4)
rem  OS   : Windows 10 1803+ / Windows 11, 64-bit
rem  Disk : ~20 GB free  |  Net: ~3 GB download on first run
rem  Everything goes into ONE folder. No admin rights, no PATH
rem  changes, no registry writes. Uninstall = delete the folder.
rem  Re-running is safe: finished steps are skipped automatically.
rem  ENCODING: the final install.bat is ANSI/GBK. Do NOT convert it
rem  to UTF-8 and do NOT add "chcp 65001" - that combo desyncs the
rem  cmd line reader after multibyte text and executes garbage
rem  fragments. Edit builder/install.tpl.bat and rebuild instead.
rem  PowerShell blocks are embedded as -EncodedCommand base64
rem  (UTF-16LE) to be immune to cmd quoting; dynamic values are
rem  passed via environment variables (RDNA4_*).
rem ==================================================================

set "PY_VER=3.12.10"
set "PY_FALLBACK=3.12.9"
set "ROCM_REL=7.2.1"
set "TORCH_VER=2.9.1"
set "ROCM_BASE=https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1"
set "APPLIO_VER=3.6.4"
set "APPLIO_ZIP_URL=https://codeload.github.com/IAHispano/Applio/zip/refs/tags/3.6.4"
set "PYPI_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "HF_MIRROR=https://hf-mirror.com"

set "INSTDIR=C:\Applio-RDNA4"
if not "%~1"=="" set "INSTDIR=%~1"
if "%INSTDIR:~-1%"=="\" set "INSTDIR=%INSTDIR:~0,-1%"

echo.
echo  ==================================================
echo    Applio ROCm RDNA4 一键安装
echo    AMD RX 9000 系列 · Windows 64 位
echo  ==================================================
echo.
echo    安装位置 : %INSTDIR%
echo.
echo    前提条件:
echo      - AMD RX 9000 系列显卡, 驱动 26.2.2 或更新
echo      - 约 20 GB 可用磁盘空间
echo      - 全程联网, 首次下载约 3 GB, 磁盘占用约 10 GB
echo.
echo    全部文件装进一个独立文件夹, 不修改系统 Python,
echo    不写环境变量, 不需要管理员权限, 删除目录即完全卸载。
echo    安装中断后重新双击本脚本即可续装, 已完成步骤自动跳过。
echo.
echo    按任意键开始 ...
pause >nul

echo.
echo [1/9] 前置检测
where curl >nul 2>nul
if errorlevel 1 goto no_curl
where tar >nul 2>nul
if errorlevel 1 goto no_tar
powershell -NoProfile -EncodedCommand JABnACAAPQAgACgARwBlAHQALQBDAGkAbQBJAG4AcwB0AGEAbgBjAGUAIABXAGkAbgAzADIAXwBWAGkAZABlAG8AQwBvAG4AdAByAG8AbABsAGUAcgApAC4ATgBhAG0AZQAgAC0AagBvAGkAbgAgACcAIAA7ACAAJwAKAFcAcgBpAHQAZQAtAEgAbwBzAHQAIAAoACcAIAAgAEcAUABVADoAIAAnACAAKwAgACQAZwApAAoAaQBmACAAKAAkAGcAIAAtAG0AYQB0AGMAaAAgACcAUgBYACAAOQBbADAALQA5AF0AWwAwAC0AOQBdACcAKQAgAHsAIABlAHgAaQB0ACAAMAAgAH0AIABlAGwAcwBlACAAewAgAGUAeABpAHQAIAAxACAAfQAKAA==
if not errorlevel 1 goto gpu_ok
echo   [警告] 未检测到 AMD RX 9000 系列显卡
echo   本安装器仅适用于 RX 9000 系列 RDNA4 显卡
echo   确认继续请按 Y, 退出请按 N, 30 秒后自动退出
choice /c YN /n /t 30 /d N >nul
if errorlevel 2 goto aborted
:gpu_ok
set "INSTDRIVE=%INSTDIR:~0,1%"
set "RDNA4_DRIVE=%INSTDRIVE%"
powershell -NoProfile -EncodedCommand JABkACAAPQAgACQAZQBuAHYAOgBSAEQATgBBADQAXwBEAFIASQBWAEUACgAkAGYAIAA9ACAAKABHAGUAdAAtAFAAUwBEAHIAaQB2AGUAIAAkAGQAKQAuAEYAcgBlAGUAIAAvACAAMQBHAEIACgBXAHIAaQB0AGUALQBIAG8AcwB0ACAAKAAnACAAIAAnACAAKwAgACQAZAAgACsAIAAnADoAIABmAHIAZQBlACAAJwAgACsAIABbAGkAbgB0AF0AJABmACAAKwAgACcAIABHAEIAJwApAAoAaQBmACAAKAAkAGYAIAAtAGwAdAAgADIAMAApACAAewAgAGUAeABpAHQAIAAxACAAfQAgAGUAbABzAGUAIAB7ACAAZQB4AGkAdAAgADAAIAB9AAoA
if not errorlevel 1 goto disk_ok
echo   [警告] 目标磁盘剩余空间不足 20 GB, 安装可能失败
echo   换位置请按 N 退出后用命令指定: install.bat 盘符:\路径
echo   确认继续请按 Y, 30 秒后自动退出
choice /c YN /n /t 30 /d N >nul
if errorlevel 2 goto aborted
:disk_ok
echo   检测通过

echo.
echo [2/9] 创建安装目录
if not exist "%INSTDIR%" mkdir "%INSTDIR%" 2>nul
if exist "%INSTDIR%" goto dir_ok
echo   目录 %INSTDIR% 不可创建, 改用备用位置
set "INSTDIR=%LOCALAPPDATA%\Programs\Applio-RDNA4"
if not exist "%INSTDIR%" mkdir "%INSTDIR%"
:dir_ok
echo ok> "%INSTDIR%\.wtest" 2>nul
if errorlevel 1 goto no_dir
del "%INSTDIR%\.wtest" >nul 2>nul
set "RUNTIME=%INSTDIR%\runtime"
set "CACHE=%INSTDIR%-cache"
if not exist "%CACHE%" mkdir "%CACHE%"
echo   目录就绪: %INSTDIR%

echo.
echo [3/9] 安装 Python %PY_VER% 到独立目录
if exist "%RUNTIME%\python.exe" goto py_done
rem 优先用官方 nuget 便携包: 纯解压, 免 MSI, 机器上已装同版本
rem Python 时安装器会忽略 TargetDir 走原地修复(实测 3.12.10), nuget 无此问题
set "DL_URL=https://www.nuget.org/api/v2/package/python/%PY_VER%"
set "DL_FILE=python-%PY_VER%-nupkg.zip"
call :download
if exist "%CACHE%\pyzip" rd /s /q "%CACHE%\pyzip"
mkdir "%CACHE%\pyzip" 2>nul
tar -xf "%CACHE%\python-%PY_VER%-nupkg.zip" -C "%CACHE%\pyzip"
if errorlevel 1 goto py_nuget_fail
if not exist "%CACHE%\pyzip\tools\python.exe" goto py_nuget_fail
echo   解压便携版 Python ...
robocopy "%CACHE%\pyzip\tools" "%RUNTIME%" /E /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto py_nuget_fail
rd /s /q "%CACHE%\pyzip"
if not exist "%RUNTIME%\python.exe" goto py_nuget_fail
"%RUNTIME%\python.exe" -m ensurepip --upgrade >nul 2>nul
"%RUNTIME%\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 goto py_nuget_fail
goto py_done
:py_nuget_fail
echo   [提示] 便携包方式失败, 改用官方安装器 ...
set "DL_URL=https://www.python.org/ftp/python/%PY_FALLBACK%/python-%PY_FALLBACK%-amd64.exe"
set "DL_FILE=python-%PY_FALLBACK%-amd64.exe"
call :download
echo   静默安装中, 约一分钟 ...
start /wait "" "%CACHE%\python-%PY_FALLBACK%-amd64.exe" /quiet InstallAllUsers=0 TargetDir="%RUNTIME%" PrependPath=0 Include_test=0 Include_launcher=0 Shortcuts=0
if not exist "%RUNTIME%\python.exe" goto py_fail
:py_done
"%RUNTIME%\python.exe" --version

echo.
echo [4/9] 下载并安装 ROCm SDK + PyTorch 约 2.2 GB - 全程最耗时的一步
"%RUNTIME%\python.exe" -c "import torch" >nul 2>nul
if not errorlevel 1 goto torch_done
set "DL_URL=%ROCM_BASE%/rocm_sdk_core-%ROCM_REL%-py3-none-win_amd64.whl"
set "DL_FILE=rocm_sdk_core-%ROCM_REL%-py3-none-win_amd64.whl"
call :download
set "DL_URL=%ROCM_BASE%/rocm_sdk_devel-%ROCM_REL%-py3-none-win_amd64.whl"
set "DL_FILE=rocm_sdk_devel-%ROCM_REL%-py3-none-win_amd64.whl"
call :download
set "DL_URL=%ROCM_BASE%/rocm_sdk_libraries_custom-%ROCM_REL%-py3-none-win_amd64.whl"
set "DL_FILE=rocm_sdk_libraries_custom-%ROCM_REL%-py3-none-win_amd64.whl"
call :download
set "DL_URL=%ROCM_BASE%/rocm-%ROCM_REL%.tar.gz"
set "DL_FILE=rocm-%ROCM_REL%.tar.gz"
call :download
set "DL_URL=%ROCM_BASE%/torch-%TORCH_VER%+rocm%ROCM_REL%-cp312-cp312-win_amd64.whl"
set "DL_FILE=torch-%TORCH_VER%+rocm%ROCM_REL%-cp312-cp312-win_amd64.whl"
call :download
set "DL_URL=%ROCM_BASE%/torchaudio-%TORCH_VER%+rocm%ROCM_REL%-cp312-cp312-win_amd64.whl"
set "DL_FILE=torchaudio-%TORCH_VER%+rocm%ROCM_REL%-cp312-cp312-win_amd64.whl"
call :download
set "DL_URL=%ROCM_BASE%/torchvision-0.24.1+rocm%ROCM_REL%-cp312-cp312-win_amd64.whl"
set "DL_FILE=torchvision-0.24.1+rocm%ROCM_REL%-cp312-cp312-win_amd64.whl"
call :download
call :install_rocm
:torch_done
echo   验证 GPU 识别 ...
"%RUNTIME%\python.exe" -c "import torch; print('   PyTorch:', torch.__version__); print('   GPU:', torch.cuda.get_device_name(0))"
"%RUNTIME%\python.exe" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" >nul 2>nul
if errorlevel 1 goto gpu_fail

echo.
echo [5/9] 下载 Applio %APPLIO_VER% 源码
if exist "%INSTDIR%\Applio\app.py" goto applio_done
set "DL_URL=%APPLIO_ZIP_URL%"
set "DL_FILE=applio-%APPLIO_VER%.zip"
call :download
if exist "%INSTDIR%\Applio-%APPLIO_VER%" rd /s /q "%INSTDIR%\Applio-%APPLIO_VER%"
if exist "%INSTDIR%\Applio" rd /s /q "%INSTDIR%\Applio"
echo   解压中 ...
tar -xf "%CACHE%\applio-%APPLIO_VER%.zip" -C "%INSTDIR%"
if errorlevel 1 goto zip_fail
if not exist "%INSTDIR%\Applio-%APPLIO_VER%" goto zip_fail
ren "%INSTDIR%\Applio-%APPLIO_VER%" Applio
if not exist "%INSTDIR%\Applio\app.py" goto zip_fail
:applio_done
echo   源码就绪

echo.
echo [6/9] 安装依赖 - 自动过滤 torch 行, 保护 ROCm 版本
findstr /v /b "torch==" "%INSTDIR%\Applio\requirements.txt" | findstr /v /b "torchaudio==" | findstr /v /b "torchvision==" > "%CACHE%\requirements_no_torch.txt"
if not exist "%CACHE%\requirements_no_torch.txt" goto req_fail
echo   使用清华 PyPI 镜像安装, 约需几分钟 ...
"%RUNTIME%\python.exe" -m pip install --no-warn-script-location -i %PYPI_MIRROR% -r "%CACHE%\requirements_no_torch.txt"
if errorlevel 1 goto req_fail
echo   确认 ROCm torch 未被覆盖 ...
"%RUNTIME%\python.exe" -c "import torch, sys; sys.exit(0 if '+rocm' in torch.__version__ else 1)" >nul 2>nul
if not errorlevel 1 goto req_done
echo   [警告] torch 被依赖覆盖, 自动修复中 ...
call :install_rocm
"%RUNTIME%\python.exe" -c "import torch, sys; sys.exit(0 if '+rocm' in torch.__version__ else 1)" >nul 2>nul
if errorlevel 1 goto torch_broken
:req_done
echo   依赖就绪

echo.
echo [7/9] 应用 RDNA4 补丁
if not exist "%~dp0apply_rdna4_patches.py" goto no_patch_files
if not exist "%~dp0applio_cudnn_off.py" goto no_patch_files
copy /y "%~dp0applio_cudnn_off.py" "%INSTDIR%\Applio\" >nul
copy /y "%~dp0apply_rdna4_patches.py" "%INSTDIR%\Applio\" >nul
pushd "%INSTDIR%\Applio"
"%RUNTIME%\python.exe" apply_rdna4_patches.py
if errorlevel 1 goto patch_fail
popd
echo   补丁就绪

echo.
echo [8/9] 预训练模型
if exist "%INSTDIR%\Applio\tools\download_models.py" goto dl_models
echo   预训练模型需首次启动后在 WebUI 里下载:
echo     启动 Applio 后 - 设置 Settings - 训练 Train - 下载预训练模型
echo   启动器已内置国内镜像 HF_ENDPOINT, 一般可直接下载成功
goto models_done
:dl_models
set "HF_ENDPOINT=%HF_MIRROR%"
"%RUNTIME%\python.exe" "%INSTDIR%\Applio\tools\download_models.py"
if errorlevel 1 echo   [提示] 模型下载失败, 不影响安装, 可启动后在 WebUI 中下载
:models_done

echo.
echo [9/9] 生成启动器与桌面快捷方式
call :make_launchers
set "RDNA4_INSTDIR=%INSTDIR%"
powershell -NoProfile -EncodedCommand JABpAG4AcwB0ACAAPQAgACQAZQBuAHYAOgBSAEQATgBBADQAXwBJAE4AUwBUAEQASQBSAAoAJABkAGUAcwBrACAAPQAgAFsARQBuAHYAaQByAG8AbgBtAGUAbgB0AF0AOgA6AEcAZQB0AEYAbwBsAGQAZQByAFAAYQB0AGgAKAAnAEQAZQBzAGsAdABvAHAAJwApAAoAJAB3ACAAPQAgAE4AZQB3AC0ATwBiAGoAZQBjAHQAIAAtAEMAbwBtAE8AYgBqAGUAYwB0ACAAVwBTAGMAcgBpAHAAdAAuAFMAaABlAGwAbAAKACQAbAAgAD0AIABAACgAQAAoACcAQQBwAHAAbABpAG8AIACoYwZ0JwAsACAAJwByAHUAbgBfAGkAbgBmAGUAcgAuAGIAYQB0ACcAKQAsACAAQAAoACcAQQBwAHAAbABpAG8AIACti8N+JwAsACAAJwByAHUAbgBfAHQAcgBhAGkAbgAuAGIAYQB0ACcAKQApAAoAZgBvAHIAZQBhAGMAaAAgACgAJABuACAAaQBuACAAJABsACkAIAB7AAoAIAAgACQAcwAgAD0AIAAkAHcALgBDAHIAZQBhAHQAZQBTAGgAbwByAHQAYwB1AHQAKABbAEkATwAuAFAAYQB0AGgAXQA6ADoAQwBvAG0AYgBpAG4AZQAoACQAZABlAHMAawAsACAAJABuAFsAMABdACAAKwAgACcALgBsAG4AawAnACkAKQAKACAAIAAkAHMALgBUAGEAcgBnAGUAdABQAGEAdABoACAAPQAgAFsASQBPAC4AUABhAHQAaABdADoAOgBDAG8AbQBiAGkAbgBlACgAJABpAG4AcwB0ACwAIAAkAG4AWwAxAF0AKQAKACAAIAAkAHMALgBXAG8AcgBrAGkAbgBnAEQAaQByAGUAYwB0AG8AcgB5ACAAPQAgACQAaQBuAHMAdAAKACAAIAAkAHMALgBJAGMAbwBuAEwAbwBjAGEAdABpAG8AbgAgAD0AIABbAEkATwAuAFAAYQB0AGgAXQA6ADoAQwBvAG0AYgBpAG4AZQAoACQAaQBuAHMAdAAsACAAJwByAHUAbgB0AGkAbQBlAFwAcAB5AHQAaABvAG4ALgBlAHgAZQAnACkACgAgACAAJABzAC4AUwBhAHYAZQAoACkACgB9AAoAVwByAGkAdABlAC0ASABvAHMAdAAgACcAIAAgAHMAaABvAHIAdABjAHUAdABzACAAbwBrACcACgBlAHgAaQB0ACAAMAAKAA==
if errorlevel 1 echo   [提示] 快捷方式创建失败, 请直接运行安装目录下的 run_infer.bat 和 run_train.bat

echo.
echo  ==================================================
echo    安装完成!
echo  ==================================================
echo.
echo    桌面已生成两个图标, 注意不要混用:
echo.
echo      [Applio 推理]  变声/推理用 - cudnn 关闭
echo      [Applio 训练]  训练模型用 - cudnn 开启
echo.
echo    [注意] 首次启动 Applio 会自动下载模型等文件, 请确保此时联网
echo.
echo    安装目录 : %INSTDIR%
echo    启动器   : %INSTDIR%\run_infer.bat 和 run_train.bat
echo    卸载     : 运行本仓库的 uninstall.bat
echo.
pause
exit /b 0

:download
if exist "%CACHE%\%DL_FILE%.ok" goto :eof
echo   [下载] %DL_FILE%
curl -fL --retry 5 --retry-delay 2 -C - -o "%CACHE%\%DL_FILE%" "%DL_URL%"
if not errorlevel 1 goto dl_ok
set "RDNA4_DLFILE=%CACHE%\%DL_FILE%"
set "RDNA4_DLURL=%DL_URL%"
powershell -NoProfile -EncodedCommand JABmACAAPQAgACQAZQBuAHYAOgBSAEQATgBBADQAXwBEAEwARgBJAEwARQAKACQAdQAgAD0AIAAkAGUAbgB2ADoAUgBEAE4AQQA0AF8ARABMAFUAUgBMAAoAJABsACAAPQAgACgARwBlAHQALQBJAHQAZQBtACAALQBMAGkAdABlAHIAYQBsAFAAYQB0AGgAIAAkAGYAIAAtAEUAcgByAG8AcgBBAGMAdABpAG8AbgAgAFMAaQBsAGUAbgB0AGwAeQBDAG8AbgB0AGkAbgB1AGUAKQAuAEwAZQBuAGcAdABoAAoAJAByACAAPQAgADAACgB0AHIAeQAgAHsAIAAkAHIAIAA9ACAAWwBsAG8AbgBnAF0AKABJAG4AdgBvAGsAZQAtAFcAZQBiAFIAZQBxAHUAZQBzAHQAIAAtAFUAcgBpACAAJAB1ACAALQBNAGUAdABoAG8AZAAgAEgAZQBhAGQAIAAtAFUAcwBlAEIAYQBzAGkAYwBQAGEAcgBzAGkAbgBnACkALgBIAGUAYQBkAGUAcgBzAFsAJwBDAG8AbgB0AGUAbgB0AC0ATABlAG4AZwB0AGgAJwBdACAAfQAgAGMAYQB0AGMAaAAgAHsAfQAKAGkAZgAgACgAJABsACAALQBhAG4AZAAgACQAcgAgAC0AZwB0ACAAMAAgAC0AYQBuAGQAIAAkAGwAIAAtAGUAcQAgACQAcgApACAAewAgAGUAeABpAHQAIAAwACAAfQAgAGUAbABzAGUAIAB7ACAAZQB4AGkAdAAgADEAIAB9AAoA >nul 2>nul
if not errorlevel 1 goto dl_ok
echo   续传失败, 重新完整下载 %DL_FILE%
curl -fL --retry 5 --retry-delay 2 -o "%CACHE%\%DL_FILE%" "%DL_URL%"
if errorlevel 1 goto dl_fail
:dl_ok
echo ok> "%CACHE%\%DL_FILE%.ok"
goto :eof
:dl_fail
echo   [错误] 下载失败: %DL_FILE%
echo   网络恢复后重新运行 install.bat 即可断点续传
goto fail

:install_rocm
echo   安装中, 解压约 10 GB, 需要几分钟 ...
"%RUNTIME%\python.exe" -m pip install --no-warn-script-location ^
  "%CACHE%\rocm_sdk_core-%ROCM_REL%-py3-none-win_amd64.whl" ^
  "%CACHE%\rocm_sdk_devel-%ROCM_REL%-py3-none-win_amd64.whl" ^
  "%CACHE%\rocm_sdk_libraries_custom-%ROCM_REL%-py3-none-win_amd64.whl" ^
  "%CACHE%\rocm-%ROCM_REL%.tar.gz" ^
  "%CACHE%\torch-%TORCH_VER%+rocm%ROCM_REL%-cp312-cp312-win_amd64.whl" ^
  "%CACHE%\torchaudio-%TORCH_VER%+rocm%ROCM_REL%-cp312-cp312-win_amd64.whl" ^
  "%CACHE%\torchvision-0.24.1+rocm%ROCM_REL%-cp312-cp312-win_amd64.whl"
if errorlevel 1 goto wheel_fail
goto :eof

:make_launchers
> "%INSTDIR%\run_infer.bat" echo @echo off
>> "%INSTDIR%\run_infer.bat" echo title Applio RDNA4 - Inference
>> "%INSTDIR%\run_infer.bat" echo cd /d "%INSTDIR%\Applio"
>> "%INSTDIR%\run_infer.bat" echo set "HF_ENDPOINT=%HF_MIRROR%"
>> "%INSTDIR%\run_infer.bat" echo "%RUNTIME%\python.exe" applio_cudnn_off.py --open
>> "%INSTDIR%\run_infer.bat" echo pause
> "%INSTDIR%\run_train.bat" echo @echo off
>> "%INSTDIR%\run_train.bat" echo title Applio RDNA4 - Train
>> "%INSTDIR%\run_train.bat" echo cd /d "%INSTDIR%\Applio"
>> "%INSTDIR%\run_train.bat" echo set "MIOPEN_USER_DB_PATH=%%USERPROFILE%%\.miopen_applio"
>> "%INSTDIR%\run_train.bat" echo set "MIOPEN_DEBUG_CONV_FFT=0"
>> "%INSTDIR%\run_train.bat" echo set "MIOPEN_FIND_MODE=FAST"
>> "%INSTDIR%\run_train.bat" echo set "HF_ENDPOINT=%HF_MIRROR%"
>> "%INSTDIR%\run_train.bat" echo set "PATH=%RUNTIME%\Lib\site-packages\_rocm_sdk_core\lib\llvm\bin;%%PATH%%"
>> "%INSTDIR%\run_train.bat" echo "%RUNTIME%\python.exe" app.py --open
>> "%INSTDIR%\run_train.bat" echo pause
goto :eof

:no_curl
echo   [错误] 系统缺少 curl, 请升级到 Windows 10 1803 以上版本
goto fail
:no_tar
echo   [错误] 系统缺少 tar, 请升级到 Windows 10 1803 以上版本
goto fail
:aborted
echo.
echo  已取消安装, 未做任何修改
pause
exit /b 1
:no_dir
echo   [错误] 无法创建安装目录 %INSTDIR%
echo   可换一个位置: 在 cmd 中运行 install.bat 盘符:\路径
goto fail
:py_fail
echo   [错误] Python 安装失败
echo   安装器日志在 %TEMP% 下, 文件名以 Python 开头, 可截图反馈到仓库 issues
goto fail
:wheel_fail
echo   [错误] ROCm / PyTorch 安装失败, 重新运行 install.bat 会自动重试
goto fail
:gpu_fail
echo   [错误] GPU 未被识别, 请确认显卡驱动为 26.2.2 或更新版本后重试
goto fail
:zip_fail
echo   [错误] Applio 源码解压失败, 删除 %CACHE%\applio-%APPLIO_VER%.zip 后重试
goto fail
:req_fail
echo   [错误] 依赖安装失败, 多为网络问题, 重新运行 install.bat 会自动重试
goto fail
:no_patch_files
echo   [错误] 当前目录未找到 applio_cudnn_off.py 和 apply_rdna4_patches.py
echo   请用 GitHub 页面 Code 按钮下载完整 ZIP 解压后再运行
goto fail
:patch_fail
popd
echo   [错误] RDNA4 补丁未完全命中, 请确认 Applio 版本为 3.6.4
goto fail
:torch_broken
echo   [错误] torch 修复失败, 请把上方报错截图反馈到仓库 issues
goto fail
:fail
echo.
echo  安装中断。解决问题后重新运行 install.bat 即可, 已完成步骤会自动跳过
pause
exit /b 1
