"""
转录文本服务
============
管理课堂转录文本和课程资料的读写
"""

import os
import re
import shutil
import hashlib
from datetime import datetime, timedelta

from config import DATA_DIR, CITE_DIR


class TranscriptService:
    """转录文本管理服务"""

    SUMMARY_START_MARKER = "=== 历史摘要 开始 ==="
    SUMMARY_END_MARKER = "=== 历史摘要 结束 ==="

    def __init__(self):
        self.transcript_path = os.path.join(DATA_DIR, "class_transcript.txt")
        self.material_path = os.path.join(DATA_DIR, "current_class_material.txt")
        self.cite_dir = CITE_DIR

    def get_recent_transcript(self, minutes: int = 2) -> str:
        """
        获取最近 N 分钟的转录文本

        Args:
            minutes: 向前回溯的分钟数，默认 2 分钟

        Returns:
            最近的转录文本
        """
        if not os.path.exists(self.transcript_path):
            return ""

        with open(self.transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return ""

        # 只统计「最后一次会话」的内容：以最后一个「课堂记录 开始于」标记为界。
        # 原因（对应审查报告 B4）：转录行时间戳只有 HH:MM:SS、不含日期，
        # 若转录文件里残留着上一节课的记录，其同时间段的行会被误判为
        # 「最近 N 分钟」，混入救场 / 进度总结的上下文。
        session_start_index = 0
        for idx, raw_line in enumerate(lines):
            if raw_line.strip().startswith("=== 课堂记录 开始于"):
                session_start_index = idx

        # 解析带有时间戳的行，筛选最近 N 分钟的内容
        now = datetime.now()
        cutoff = now - timedelta(minutes=minutes)
        recent_lines = []
        in_summary_block = False

        for line in lines[session_start_index:]:
            line = line.strip()
            if not line or line.startswith("==="):
                if line == self.SUMMARY_START_MARKER:
                    in_summary_block = True
                elif line == self.SUMMARY_END_MARKER:
                    in_summary_block = False
                continue

            if in_summary_block:
                continue

            # 尝试解析时间戳格式 [HH:MM:SS]
            if line.startswith("[") and "]" in line:
                try:
                    time_str = line[1:line.index("]")]
                    line_time = datetime.strptime(time_str, "%H:%M:%S").replace(
                        year=now.year, month=now.month, day=now.day
                    )
                    if line_time >= cutoff:
                        recent_lines.append(line)
                except ValueError:
                    recent_lines.append(line)  # 解析失败则保留
            else:
                recent_lines.append(line)

        return "\n".join(recent_lines)

    def get_full_transcript(self) -> str:
        """获取完整的课堂转录文本"""
        if not os.path.exists(self.transcript_path):
            return ""

        with open(self.transcript_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_transcript_metadata(self) -> dict:
        """从转录文件头部提取课程和资料元数据。"""
        metadata = {
            "course_name": "",
            "material_name": "",
        }

        if not os.path.exists(self.transcript_path):
            return metadata

        with open(self.transcript_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("课程："):
                    metadata["course_name"] = line.split("课程：", 1)[1].strip()
                    continue
                if line.startswith("参考资料："):
                    metadata["material_name"] = line.split("参考资料：", 1)[1].strip()
                    continue
                if re.match(r"^\[\d{2}:\d{2}:\d{2}\]", line):
                    break

        return metadata

    def get_class_material(self) -> str:
        """获取课程 PPT 资料文本"""
        if not os.path.exists(self.material_path):
            return ""

        with open(self.material_path, "r", encoding="utf-8") as f:
            return f.read()

    def list_cite_files(self) -> list[dict]:
        """列出 cite 目录下可选的资料文本。"""
        if not os.path.exists(self.cite_dir):
            return []

        items = []
        for name in os.listdir(self.cite_dir):
            if not name.lower().endswith(".txt"):
                continue
            file_path = os.path.join(self.cite_dir, name)
            stat = os.stat(file_path)
            items.append({
                "filename": name,
                "updated_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "size": stat.st_size,
            })

        items.sort(key=lambda item: item["updated_at"], reverse=True)
        return items

    def activate_cite_file(self, filename: str | None) -> str:
        """将某个 cite 文本设为当前课程资料；None 表示清空。"""
        if not filename:
            with open(self.material_path, "w", encoding="utf-8") as f:
                f.write("")
            return ""

        source_path = os.path.join(self.cite_dir, filename)
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"未找到 cite 文件: {filename}")

        shutil.copyfile(source_path, self.material_path)
        return source_path

    def get_transcript_snapshot(self, since_mtime: float | None = None) -> dict:
        """返回 transcript 快照，供前端轮询时快速判断是否变化。"""
        if not os.path.exists(self.transcript_path):
            return {
                "exists": False,
                "changed": False,
                "mtime": None,
                "line_count": 0,
                "sha1": "",
                "content": "",
            }

        stat = os.stat(self.transcript_path)
        mtime = stat.st_mtime
        if since_mtime is not None and mtime <= since_mtime:
            return {
                "exists": True,
                "changed": False,
                "mtime": mtime,
                "line_count": 0,
                "sha1": "",
                "content": "",
            }

        content = self.get_full_transcript()
        sha1 = hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()
        return {
            "exists": True,
            "changed": True,
            "mtime": mtime,
            "line_count": len(content.splitlines()),
            "sha1": sha1,
            "content": content,
        }
