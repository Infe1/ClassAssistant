"""
课程资料上传路由
================
处理 PPT / PDF / Word 文件上传与文本提取
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from services.ppt_service import parse_material
import os
import re
import tempfile
from datetime import datetime
from config import DATA_DIR, CITE_DIR

router = APIRouter()

# 支持的文件扩展名。
# 注意：.ppt / .doc（Office 2003 二进制老格式）**不在其中** ——
# python-pptx / python-docx 只支持 OOXML（.pptx / .docx），
# 把它们列入白名单会让用户误以为可上传，实际必然在打开阶段失败。
ALLOWED_EXTENSIONS = ('.pptx', '.pdf', '.docx')

# 老格式：单独识别并给出转换引导，而不是抛笼统的"解析失败"
LEGACY_EXTENSIONS = ('.ppt', '.doc')
LEGACY_HINT = (
    "不支持 {ext} 格式（Office 2003 老格式）。"
    "请先用 Office / WPS 打开并「另存为」.pptx 或 .docx，再上传。"
)


def _build_safe_stem(filename: str) -> str:
    stem = os.path.splitext(filename)[0].strip() or "cite"
    stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", stem)
    return stem[:60].strip("_") or "cite"


@router.post("/upload_ppt")
async def upload_ppt(file: UploadFile = File(...)):
    """
    上传课程资料文件并解析为纯文本
    支持格式: .pptx, .pdf, .docx
    """
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    # 老格式单独提示，避免用户拿到一句没有引导的「解析失败」
    if ext in LEGACY_EXTENSIONS:
        raise HTTPException(status_code=400, detail=LEGACY_HINT.format(ext=ext))

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式，仅支持: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await file.read()

    # 临时文件改用 mkstemp：每次生成唯一文件名，
    # 避免两个并发上传（或前端重试）写入同一路径互相覆盖。
    fd, temp_path = tempfile.mkstemp(suffix=ext, dir=DATA_DIR)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)

        # 调用统一解析服务
        text = parse_material(temp_path, filename)

        # 将解析结果保存到 cite 目录，供开始摸鱼时选择
        os.makedirs(CITE_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cite_filename = f"{_build_safe_stem(filename)}_{timestamp}.txt"
        material_path = os.path.join(CITE_DIR, cite_filename)
        with open(material_path, "w", encoding="utf-8") as f:
            f.write(text)

        return {
            "status": "success",
            "message": f"成功解析并保存到 cite: {cite_filename}",
            "text_length": len(text),
            "cite_filename": cite_filename,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件解析失败: {str(e)}")
    finally:
        # 成功与失败路径都清理临时文件（此前失败会残留 data/temp_upload.*）
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
