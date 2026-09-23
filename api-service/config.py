"""
全局配置
========
集中管理 DATA_DIR 等路径，兼容开发模式和 PyInstaller 打包模式
"""

import os
import sys
from datetime import datetime

# 应用版本号。
# 后端没有像前端 app-ui/package.json 那样的构建期单一来源，此处手工维护；
# 改版本号时需与 app-ui/package.json 保持一致（发布前核对）。
APP_VERSION = "2.0.5"

if getattr(sys, 'frozen', False):
    # PyInstaller 打包模式：exe 位于 release/backend/，data 在 release/data/
    _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    PROJECT_ROOT = os.path.dirname(_exe_dir)
else:
    # 开发模式：本文件位于 api-service/config.py，项目根目录在上一级
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CITE_DIR = os.path.join(DATA_DIR, "cite")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "summaries"), exist_ok=True)
os.makedirs(CITE_DIR, exist_ok=True)

# 启动日志：方便确认打包版路径是否正确。
# 采用「追加 + 时间戳」而非覆盖 —— 此前用 "w"，多次启动（或多进程）时只留最后一次，
# 排查启动顺序 / 重复启动问题时信息不足。
try:
    _log_path = os.path.join(DATA_DIR, "_startup.log")
    with open(_log_path, "a", encoding="utf-8") as _f:
        _f.write(
            "[%s] frozen=%s executable=%s PROJECT_ROOT=%s DATA_DIR=%s\n"
            % (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                getattr(sys, "frozen", False),
                sys.executable,
                PROJECT_ROOT,
                DATA_DIR,
            )
        )
except Exception:
    pass
