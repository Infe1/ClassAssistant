# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for ClassFox Lite Backend (Slim)
Bundles FastAPI + webspeech/sherpa-onnx services into a single directory
"""

import os
import sys

block_cipher = None

# Collect all service and router Python files as data
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'fastapi',
        'starlette',
        'starlette.routing',
        'starlette.responses',
        'starlette.middleware',
        'starlette.middleware.cors',
        'pydantic',
        'multipart',
        'python_multipart',
        'routers',
        'routers.ppt_router',
        'routers.monitor_router',
        'routers.rescue_router',
        'routers.summary_router',
        'routers.settings_router',
        'services',
        'services.asr_service',
        'services.llm_service',
        'services.monitor_service',
        'services.ppt_service',
        'services.summary_service',
        'services.transcript_service',
        'config',
        'pyaudio',
        'pptx',
        'pypdf',
        'docx',
        'openai',
        'dotenv',
        'gzip',
        'aiofiles',
        'httptools',
        'websockets',
        'sherpa_onnx',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'speech_recognition',
        'winsdk',
        'dashscope',
        'websocket',
        'numpy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='class-fox-lite-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

# Filter out corrupted DLLs picked up from tesseract on system PATH
excluded_dlls = {'libfribidi-0.dll'}
filtered_binaries = [b for b in a.binaries if b[0].lower() not in excluded_dlls]

coll = COLLECT(
    exe,
    filtered_binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='class-fox-lite-backend',
)
