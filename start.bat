@echo off
:: 设置代码页为 UTF-8 以支持中文显示
chcp 65001 >nul

setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo ==================================================
echo           MomentWeaver Windows 启动脚本
echo ==================================================

:: 检查并激活虚拟环境
if exist "%ROOT_DIR%.venv\" (
    echo [信息] 检测到虚拟环境，正在激活...
    call "%ROOT_DIR%.venv\Scripts\activate.bat"
    if not defined MOMENTWEAVER_PYTHON (
        set "MOMENTWEAVER_PYTHON=%ROOT_DIR%.venv\Scripts\python.exe"
    )
)

:: 确定 Python 执行命令
if not defined MOMENTWEAVER_PYTHON (
    set "PYTHON_BIN=python"
) else (
    set "PYTHON_BIN=%MOMENTWEAVER_PYTHON%"
)

:: 验证 Python 是否可用
"%PYTHON_BIN%" --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到 Python 或 Python 无法执行: %PYTHON_BIN%
    echo 请确保已安装 Python 并将其添加到系统 PATH 中，或者设置 MOMENTWEAVER_PYTHON 环境变量。
    echo 示例: set MOMENTWEAVER_PYTHON=C:\path\to\python.exe
    echo.
    pause
    exit /b 1
)

:: 检查 Python 依赖
"%PYTHON_BIN%" -c "import fastapi, uvicorn, PIL" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] 当前 Python 环境中缺少必要的依赖库 (fastapi, uvicorn, PIL 等)。
    echo 请运行以下命令安装依赖：
    echo   "%PYTHON_BIN%" -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

:: 加载 .env 配置文件
if exist "%ROOT_DIR%.env" (
    echo [信息] 正在加载 .env 配置文件...
    for /f "usebackq tokens=1,* delims==" %%i in ("%ROOT_DIR%.env") do (
        set "key=%%i"
        set "val=%%j"
        call :process_line
    )
)

:: 设置默认配置项
if not defined MOMENTWEAVER_HOST set "MOMENTWEAVER_HOST=127.0.0.1"
if not defined MOMENTWEAVER_PORT set "MOMENTWEAVER_PORT=8787"
if not defined MOMENTWEAVER_RELOAD set "MOMENTWEAVER_RELOAD=0"

:: 设置 PYTHONPATH
if defined PYTHONPATH (
    set "PYTHONPATH=%ROOT_DIR%backend;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%ROOT_DIR%backend"
)

echo.
echo [信息] 正在启动 MomentWeaver...
echo [信息] Python 路径: %PYTHON_BIN%
echo [信息] 访问地址:   http://%MOMENTWEAVER_HOST%:%MOMENTWEAVER_PORT%
echo ==================================================
echo.

if "%MOMENTWEAVER_RELOAD%"=="1" (
    "%PYTHON_BIN%" -m uvicorn app.main:app --host "%MOMENTWEAVER_HOST%" --port "%MOMENTWEAVER_PORT%" --reload
) else (
    "%PYTHON_BIN%" -m uvicorn app.main:app --host "%MOMENTWEAVER_HOST%" --port "%MOMENTWEAVER_PORT%"
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo [错误] MomentWeaver 异常退出，退出码: %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)

endlocal
exit /b 0

:: 处理 .env 每一行的子程序
:process_line
if "%key%"=="" exit /b
set "first_char=%key:~0,1%"
if "%first_char%"=="#" exit /b
:: 去除键名中的空格
set "key=%key: =%"
:: 去除值中的双引号或单引号
if defined val (
    set "val=%val:"=%"
    set "val=%val:'=%"
)
:: 动态设置环境变量
set "%key%=%val%"
exit /b
