"""
设置路由
========
管理后端 .env 配置，供前端设置面板读写。
"""

import os
import sys

from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel


router = APIRouter()


if getattr(sys, 'frozen', False):
    ENV_PATH = os.path.join(os.path.dirname(sys.executable), '.env')
else:
    ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')


class SettingsUpdateRequest(BaseModel):
    content: str


@router.get("/settings")
async def get_settings():
    if not os.path.exists(ENV_PATH):
        return {"status": "success", "content": "", "path": ENV_PATH}

    with open(ENV_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    return {"status": "success", "content": content, "path": ENV_PATH}


@router.post("/settings")
async def update_settings(request: SettingsUpdateRequest):
    try:
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(request.content.rstrip() + "\n")

        load_dotenv(ENV_PATH, override=True)
        # LLM 相关配置（模型 / 密钥 / 超时）在下次调用时会按签名自动重建客户端，
        # 无需重启；只有监听端口 API_PORT 必须重启进程才能变更。
        return {
            "status": "success",
            "message": "设置已保存并已同步到当前进程（API_PORT 变更需重启应用生效）。",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存设置失败: {exc}")