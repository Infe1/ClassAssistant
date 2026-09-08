# ==========================================
#   课狐 ClassFox - 一键打包脚本
#   用法: .\build.ps1 <版本号>
#   示例: .\build.ps1 v1.2.0
# ==========================================

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Version
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ---------- 配置（按需修改） ----------
$VENV_DIR = Join-Path $PSScriptRoot "api-service\.venv"
$VENV_PYINSTALLER = Join-Path $VENV_DIR "Scripts\pyinstaller.exe"
# --------------------------------------

$VER_NUM = $Version -replace '^[vV]', ''
$ROOT = $PSScriptRoot
$API_DIR = Join-Path $ROOT "api-service"
$UI_DIR = Join-Path $ROOT "app-ui"
$RELEASE_DIR = Join-Path $ROOT "release"
$DIST_NAME = "ClassFox-$Version-win-x64"

$tauriConfigPath = Join-Path $UI_DIR "src-tauri\tauri.conf.json"
$tauriConfig = [IO.File]::ReadAllText($tauriConfigPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
$APP_NAME = $tauriConfig.productName
$RELEASE_EXE_NAME = "$APP_NAME.exe"

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  课狐 ClassFox - 打包 $Version" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# ================================================
# [1/6] 更新版本号
# ================================================
Write-Host "[1/6] 更新版本号为 $VER_NUM ..." -ForegroundColor Yellow

# tauri.conf.json
$file = Join-Path $UI_DIR "src-tauri\tauri.conf.json"
$content = [IO.File]::ReadAllText($file)
$content = $content -replace '"version":\s*"[^"]+"', "`"version`": `"$VER_NUM`""
[IO.File]::WriteAllText($file, $content)

# package.json
$file = Join-Path $UI_DIR "package.json"
$content = [IO.File]::ReadAllText($file)
$content = $content -replace '"version":\s*"[^"]+"', "`"version`": `"$VER_NUM`""
[IO.File]::WriteAllText($file, $content)

# Cargo.toml（仅替换 [package] 下的 version）
$file = Join-Path $UI_DIR "src-tauri\Cargo.toml"
$content = [IO.File]::ReadAllText($file)
$content = $content -replace '(?m)^version\s*=\s*"[^"]+"', "version = `"$VER_NUM`""
[IO.File]::WriteAllText($file, $content)

Write-Host "      version updated" -ForegroundColor Green

# ================================================
# [2/6] 打包后端（PyInstaller + .venv）
# ================================================
Write-Host ""
Write-Host "[2/6] 打包后端 (PyInstaller) ..." -ForegroundColor Yellow

# 检查 .venv 是否存在
if (-not (Test-Path $VENV_PYINSTALLER)) {
    Write-Host "[error] .venv not found. Run: python -m venv api-service\\.venv and install dependencies first." -ForegroundColor Red
    exit 1
}

# 构建期间去掉 tesseract 路径，避免 PyInstaller 拾取损坏的 libfribidi-0.dll
$origPath = $env:PATH
$env:PATH = ($env:PATH -split ';' | Where-Object { $_ -notmatch 'tesseract' }) -join ';'

Push-Location $API_DIR
try {
    & $VENV_PYINSTALLER backend.spec --clean --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
}
catch {
    Pop-Location
    $env:PATH = $origPath
    Write-Host "[error] backend build failed" -ForegroundColor Red
    exit 1
}
Pop-Location
$env:PATH = $origPath

Write-Host "      后端打包完成" -ForegroundColor Green

# ================================================
# [3/6] 打包前端（Tauri）
# ================================================
Write-Host ""
Write-Host "[3/6] 打包前端 (Tauri) ..." -ForegroundColor Yellow

Push-Location $UI_DIR
try {
    # --no-bundle: 只编译 exe，跳过 MSI/NSIS 安装包（我们用 zip 分发）
    npx tauri build --no-bundle
    if ($LASTEXITCODE -ne 0) { throw "Tauri build failed" }
}
catch {
    Pop-Location
    Write-Host "[error] frontend build failed" -ForegroundColor Red
    exit 1
}
Pop-Location

Write-Host "      前端打包完成" -ForegroundColor Green

# ================================================
# [4/6] 组装 release 目录
# ================================================
Write-Host ""
Write-Host "[4/6] 组装发布目录 ..." -ForegroundColor Yellow

# 清理旧 release
if (Test-Path $RELEASE_DIR) { Remove-Item $RELEASE_DIR -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $RELEASE_DIR "backend") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $RELEASE_DIR "data\summaries") -Force | Out-Null

# 复制后端
Write-Host "      复制后端文件 ..."
$backendDist = Join-Path $API_DIR "dist\class-fox-lite-backend"
Copy-Item "$backendDist\*" (Join-Path $RELEASE_DIR "backend") -Recurse -Force
Copy-Item (Join-Path $API_DIR ".env.example") (Join-Path $RELEASE_DIR "backend\.env.example") -Force
Copy-Item (Join-Path $API_DIR ".env.example") (Join-Path $RELEASE_DIR "backend\.env") -Force

# 复制 sherpa 本地模型（只带 int8 量化版 + tokens，约 48MB）
$sherpaModelName = "sherpa-onnx-streaming-zipformer-small-bilingual-zh-en-2023-02-16"
$sherpaSrc = Join-Path $ROOT "models\$sherpaModelName"
if (Test-Path $sherpaSrc) {
    Write-Host "      复制 sherpa 模型 (int8) ..."
    $sherpaDst = Join-Path $RELEASE_DIR "models\$sherpaModelName"
    New-Item -ItemType Directory -Path $sherpaDst -Force | Out-Null
    Copy-Item (Join-Path $sherpaSrc "tokens.txt") $sherpaDst -Force
    Copy-Item (Get-Item (Join-Path $sherpaSrc "encoder-*.int8.onnx")) $sherpaDst -Force
    Copy-Item (Get-Item (Join-Path $sherpaSrc "decoder-*.int8.onnx")) $sherpaDst -Force
    Copy-Item (Get-Item (Join-Path $sherpaSrc "joiner-*.int8.onnx")) $sherpaDst -Force
}
else {
    Write-Host "      [warn] 未找到 sherpa 模型目录 ($sherpaSrc)，发布包将不含本地识别模型" -ForegroundColor Yellow
}

# 复制前端 exe（尝试 productName，回退到 Cargo name）
Write-Host "      复制前端文件 ..."
$tauriRelease = Join-Path $UI_DIR "src-tauri\target\release"
$exeName = "$APP_NAME.exe"
$exePath = Join-Path $tauriRelease $exeName
$exePathAlt = Join-Path $tauriRelease "app-ui.exe"

if (Test-Path $exePath) {
    Copy-Item $exePath (Join-Path $RELEASE_DIR $RELEASE_EXE_NAME) -Force
}
elseif (Test-Path $exePathAlt) {
    Copy-Item $exePathAlt (Join-Path $RELEASE_DIR $RELEASE_EXE_NAME) -Force
}
else {
    Write-Host "[error] frontend exe not found" -ForegroundColor Red
    Write-Host "       checked: $exePath" -ForegroundColor Red
    Write-Host "       checked: $exePathAlt" -ForegroundColor Red
    exit 1
}

# 复制数据文件
Write-Host "      复制数据文件 ..."
$kw = Join-Path $ROOT "data\keywords.txt"
if (Test-Path $kw) {
    Copy-Item $kw (Join-Path $RELEASE_DIR "data\keywords.txt") -Force
}

# 复制端口示例文档
$portExamples = Join-Path $ROOT "docs\ports-examples.md"
if (Test-Path $portExamples) {
    Copy-Item $portExamples (Join-Path $RELEASE_DIR "ports-examples.md") -Force
}

Write-Host "      发布目录组装完成" -ForegroundColor Green

# ================================================
# [5/6] 验证打包后端可正常启动
# ================================================
Write-Host ""
Write-Host "[5/6] 验证打包后端可正常启动 ..." -ForegroundColor Yellow

# 使用临时 .env 和专用端口，避免与开发环境冲突
$testPort = 18765
$testEnv = Join-Path $RELEASE_DIR "backend\.env"
$releaseEnvBackup = $null
$testEnvContent = "API_PORT=$testPort`nASR_MODE=mock`n"
[string]$releaseEnvBackup = [IO.File]::ReadAllText($testEnv)
[IO.File]::WriteAllText($testEnv, $testEnvContent)

$backendExe = Join-Path $RELEASE_DIR "backend\class-fox-lite-backend.exe"
$proc = $null
$testOk = $false
$startupDeadlineSec = 20

try {
    $proc = Start-Process -FilePath $backendExe -WorkingDirectory (Join-Path $RELEASE_DIR "backend") -PassThru -WindowStyle Hidden

    for ($second = 1; $second -le $startupDeadlineSec; $second++) {
        Start-Sleep -Seconds 1

        if ($proc.HasExited) {
            Write-Host "      [失败] 后端进程启动后退出 (exit code: $($proc.ExitCode))" -ForegroundColor Red
            break
        }

        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$testPort/api/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                Write-Host "      [ok] backend health check passed (~${second}s)" -ForegroundColor Green
                $testOk = $true
                break
            }
        }
        catch {
            if ($second -eq $startupDeadlineSec) {
                Write-Host "      [fail] could not reach backend within $startupDeadlineSec seconds: $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }
}
catch {
    Write-Host "      [fail] backend start failed: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    if ($proc -and !$proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    if ($null -ne $releaseEnvBackup) {
        [IO.File]::WriteAllText($testEnv, $releaseEnvBackup)
    }
}

if (-not $testOk) {
    Write-Host ""
    Write-Host "      backend validation failed; inspect the issue and re-run packaging" -ForegroundColor Red
    Write-Host "      release directory kept for debugging: $RELEASE_DIR" -ForegroundColor Yellow
    exit 1
}

# ================================================
# [6/6] 压缩为 zip
# ================================================
Write-Host ""
Write-Host "[6/6] 压缩为 $DIST_NAME.zip ..." -ForegroundColor Yellow

$zipPath = Join-Path $ROOT "$DIST_NAME.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$RELEASE_DIR\*" -DestinationPath $zipPath -Force

$zipSizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)

Write-Host "      zip created" -ForegroundColor Green

# ================================================
# 完成
# ================================================
Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "  packaging complete" -ForegroundColor Green
Write-Host "  version: $Version" -ForegroundColor Green
Write-Host "  output:  $DIST_NAME.zip ($zipSizeMB MB)" -ForegroundColor Green
Write-Host "  folder:  release\\" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
