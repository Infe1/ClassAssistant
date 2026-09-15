"""
课堂总结服务
============
复用现有转录与 LLM 逻辑，生成并保存课堂总结文件。
"""

import os
import re
from datetime import datetime

from config import DATA_DIR
from services.llm_service import LLMService
from services.transcript_service import TranscriptService


class SummaryService:
    """负责生成并保存课堂总结。"""

    def __init__(self):
        self._llm_service = LLMService()
        self._transcript_service = TranscriptService()

    def _sanitize_filename(self, name: str) -> str:
        cleaned = re.sub(r'[\\/:*?"<>|]+', '_', (name or '').strip())
        cleaned = re.sub(r'\s+', '_', cleaned)
        return cleaned.strip('._') or '课堂笔记'

    async def generate_summary(self, course_name: str | None = None) -> dict:
        full_transcript = self._transcript_service.get_full_transcript()
        class_material = self._transcript_service.get_class_material()

        if not full_transcript.strip():
            raise ValueError("没有课堂记录可供总结")

        transcript_meta = self._transcript_service.get_transcript_metadata()
        resolved_course_name = (course_name or transcript_meta.get("course_name") or "课堂笔记").strip()

        summary_md = await self._llm_service.generate_class_summary(
            transcript=full_transcript,
            material=class_material,
        )

        # 兜底防线：即使 LLM 服务出现意外，也绝不允许写出 0 字节的总结文件。
        if not summary_md or not summary_md.strip():
            raise ValueError(
                "LLM 返回了空内容，未生成总结文件。"
                "请检查模型是否可用（思考型模型可能需要更大的 SUMMARY_MAX_TOKENS）。"
            )

        summaries_dir = os.path.join(DATA_DIR, "summaries")
        os.makedirs(summaries_dir, exist_ok=True)

        now = datetime.now()
        date_part = now.strftime("%Y%m%d")
        time_part = now.strftime("%H%M%S")
        safe_course_name = self._sanitize_filename(resolved_course_name)
        filename = f"{safe_course_name}_{date_part}_{time_part}.md"
        filepath = os.path.join(summaries_dir, filename)

        with open(filepath, "w", encoding="utf-8") as file_obj:
            file_obj.write(summary_md)

        return {
            "status": "success",
            "filename": filename,
            "summary": summary_md,
            "course_name": resolved_course_name,
        }