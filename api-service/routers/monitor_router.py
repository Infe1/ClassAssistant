"""
监控服务路由
============
处理录音启停、关键词监控、WebSocket 推送
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Optional
from services.monitor_service import MonitorService
from services.summary_service import SummaryService
from services.transcript_service import TranscriptService

router = APIRouter()

# 全局监控服务实例
monitor_service = MonitorService()
transcript_service = TranscriptService()
summary_service = SummaryService()


class KeywordUpdateRequest(BaseModel):
    """自定义关键词更新请求"""
    keywords: List[str]  # 用户自定义关键词列表


class StartMonitorRequest(BaseModel):
    course_name: str = ""
    cite_filename: Optional[str] = None
    asr_model: Optional[str] = None


class IngestAsrTextRequest(BaseModel):
    text: str
    is_final: bool = True


@router.post("/start_monitor")
async def start_monitor(request: StartMonitorRequest):
    """
    开始摸鱼模式
    - 启动麦克风录音
    - 启动 ASR 语音转文字
    - 启动关键词监控
    """
    material_name = request.cite_filename or ""
    transcript_service.activate_cite_file(material_name or None)
    result = await monitor_service.start(
        course_name=request.course_name,
        material_name=material_name,
        asr_model=request.asr_model or "",
    )
    if result.get("status") == "started":
        from os import getenv

        result["effective_asr_mode"] = getenv("ASR_MODE", "webspeech").strip().lower()
        result["webspeech_lang"] = getenv("WEBSPEECH_LANG", "zh-CN").strip() or "zh-CN"
    return result


@router.get("/transcript_snapshot")
async def get_transcript_snapshot(since_mtime: Optional[float] = None):
    snapshot = transcript_service.get_transcript_snapshot(since_mtime=since_mtime)
    return {
        "status": "success",
        **snapshot,
    }


@router.get("/cite_files")
async def get_cite_files():
    return {
        "status": "success",
        "items": transcript_service.list_cite_files(),
    }


@router.post("/stop_monitor")
async def stop_monitor():
    """
    停止监控
    - 停止录音
    - 停止 ASR
    """
    result = await monitor_service.stop()
    if result.get("status") != "stopped":
        return result

    try:
        summary_result = await summary_service.generate_summary(
            course_name=result.get("course_name") or "",
        )
        result["summary"] = {
            "filename": summary_result["filename"],
            "course_name": summary_result["course_name"],
        }
    except ValueError as exc:
        result["summary_error"] = str(exc)
    except Exception as exc:
        result["summary_error"] = f"自动总结失败: {exc}"

    return result


@router.post("/pause_monitor")
async def pause_monitor():
    return await monitor_service.pause()


@router.post("/resume_monitor")
async def resume_monitor():
    return await monitor_service.resume()


@router.post("/ingest_asr_text")
async def ingest_asr_text(request: IngestAsrTextRequest):
    """接收浏览器 Web Speech 识别结果。"""
    return await asyncio.to_thread(
        monitor_service.ingest_external_text,
        request.text,
        request.is_final,
    )


@router.get("/monitor_status")
async def monitor_status():
    return {
        "status": "success",
        "is_monitoring": monitor_service.is_monitoring,
        "is_paused": monitor_service.is_paused,
    }


@router.post("/update_keywords")
async def update_keywords(request: KeywordUpdateRequest):
    """
    更新用户自定义关键词
    - 追加到内置关键词列表中
    """
    monitor_service.update_custom_keywords(request.keywords)
    return {
        "status": "success",
        "all_keywords": monitor_service.get_all_keywords()
    }


@router.get("/keywords")
async def get_keywords():
    """获取当前所有监控关键词"""
    return {
        "builtin": monitor_service.builtin_keywords,
        "warning": monitor_service.get_warning_keywords(),
        "custom": monitor_service.custom_keywords,
        "all": monitor_service.get_all_keywords(),
        "file": monitor_service.keywords_path,
        "warning_file": monitor_service.warning_keywords_path,
    }


@router.post("/reload_keywords")
async def reload_keywords():
    """重新加载关键词文件（编辑 keywords.txt 后调用）"""
    all_kw = monitor_service.reload_keywords()
    return {
        "status": "success",
        "keywords": all_kw,
        "file": monitor_service.keywords_path,
        "warning_file": monitor_service.warning_keywords_path,
    }


@router.get("/check_mic")
async def check_mic():
    """
    检查麦克风是否可用
    - 尝试打开 PyAudio 并获取默认输入设备信息
    - 返回设备名称和可用状态
    """
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        info = p.get_default_input_device_info()
        device_name = info.get("name", "Unknown")
        sample_rate = int(info.get("defaultSampleRate", 0))
        channels = int(info.get("maxInputChannels", 0))
        p.terminate()
        return {
            "status": "ok",
            "device": device_name,
            "sample_rate": sample_rate,
            "channels": channels,
            "message": f"麦克风可用: {device_name}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"麦克风不可用: {str(e)}"
        }


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket 端点 - 实时推送点名警报
    前端连接此 WebSocket 后，当检测到关键词时会收到警报消息
    """
    await websocket.accept()
    # 注册此 WebSocket 连接到监控服务
    monitor_service.register_websocket(websocket)
    try:
        while True:
            # 保持连接，等待前端消息（如心跳）
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        monitor_service.unregister_websocket(websocket)
