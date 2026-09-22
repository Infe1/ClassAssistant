"""
LLM 服务
========
调用 OpenAI Compatible API 进行课堂问答分析和课后总结
"""

import os
import logging
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv
from services.prompt_service import PromptService

load_dotenv()

logger = logging.getLogger(__name__)

# 课后总结的 max_tokens 配置。
# 思考型模型会先产出思维链（reasoning_content），正文在思维链之后；额度不足时
# 正文会被挤成空字符串（表现为 0 字节的总结文件）。实测 20095 字转录下：
# 4000 时 5 次有 3 次正文为空，20000 稳定成功。
DEFAULT_SUMMARY_MAX_TOKENS = 20000
SUMMARY_MAX_TOKENS_FLOOR = 2000      # 低于此值思考型模型必然截断
SUMMARY_MAX_TOKENS_CEILING = 64000   # 成本/延迟护栏，防止误填超大值

# LLM 请求超时（秒）。openai SDK 默认 600 秒，对课堂场景过长：
# 一次悬停的追问会让前端「AI 思考中」卡 10 分钟，用户只能重启。
# 可用 LLM_TIMEOUT 覆盖，允许小数（如 12.5）。注意该值是「单请求总时长」，
# 课后总结在长转录 + 思考型模型下确实可能跑很久，故默认给得偏宽松。
DEFAULT_LLM_TIMEOUT = 60.0
LLM_TIMEOUT_FLOOR = 5.0
LLM_TIMEOUT_CEILING = 600.0


def resolve_llm_timeout() -> float:
    """读取 LLM_TIMEOUT，带上下界校验与日志。非法值回退默认。"""
    raw = os.getenv("LLM_TIMEOUT", "")
    if not raw or not str(raw).strip():
        return DEFAULT_LLM_TIMEOUT

    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("LLM_TIMEOUT=%r 非法，回退默认值 %.0f 秒", raw, DEFAULT_LLM_TIMEOUT)
        return DEFAULT_LLM_TIMEOUT

    if value < LLM_TIMEOUT_FLOOR:
        logger.warning(
            "LLM_TIMEOUT=%.1f 过小，已抬升到 %.1f 秒（低于该值正常请求也会被掐断）",
            value, LLM_TIMEOUT_FLOOR,
        )
        return LLM_TIMEOUT_FLOOR
    if value > LLM_TIMEOUT_CEILING:
        logger.warning(
            "LLM_TIMEOUT=%.1f 过大，已钳制到 %.1f 秒（护栏）",
            value, LLM_TIMEOUT_CEILING,
        )
        return LLM_TIMEOUT_CEILING
    return value


def resolve_summary_max_tokens() -> int:
    """读取 SUMMARY_MAX_TOKENS，带上下界校验与日志。

    每次调用都重新读取环境变量，因此在设置面板保存后无需重启即可生效。
    """
    raw = os.getenv("SUMMARY_MAX_TOKENS", "")
    if not raw or not str(raw).strip():
        return DEFAULT_SUMMARY_MAX_TOKENS

    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("SUMMARY_MAX_TOKENS=%r 非法，回退默认值 %d", raw, DEFAULT_SUMMARY_MAX_TOKENS)
        return DEFAULT_SUMMARY_MAX_TOKENS

    if value < SUMMARY_MAX_TOKENS_FLOOR:
        logger.warning(
            "SUMMARY_MAX_TOKENS=%d 过小，已抬升到 %d（低于该值思考型模型的正文会被挤空）",
            value, SUMMARY_MAX_TOKENS_FLOOR,
        )
        return SUMMARY_MAX_TOKENS_FLOOR
    if value > SUMMARY_MAX_TOKENS_CEILING:
        logger.warning(
            "SUMMARY_MAX_TOKENS=%d 过大，已钳制到 %d（成本与延迟护栏）",
            value, SUMMARY_MAX_TOKENS_CEILING,
        )
        return SUMMARY_MAX_TOKENS_CEILING
    return value


class LLMService:
    """大语言模型调用服务 - 兼容 OpenAI API"""

    def __init__(self):
        # 从环境变量读取配置
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        # 初始化异步客户端
        # timeout: 收窄 SDK 默认的 600 秒；max_retries=0 让我们自己控制重试次数，
        # 避免「超时 → 内置重试 → 再等一个超时」把卡顿放大数倍。
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=resolve_llm_timeout(),
            max_retries=0,
        )
        self.prompt_service = PromptService()

    # ------------------------------------------------------------------
    # 调用入口：统一记录 prompt 缓存命中情况
    # ------------------------------------------------------------------
    def _log_cache_usage(self, response, tag: str) -> None:
        """记录本次请求的 prompt 缓存命中量。

        各家服务商上报缓存的字段不同，这里做兼容读取：
          - DeepSeek: usage.prompt_cache_hit_tokens / prompt_cache_miss_tokens
          - OpenAI:   usage.prompt_tokens_details.cached_tokens
        都没有该字段时静默跳过（不支持的厂商不影响正常流程）。

        用途：判断「把不变内容放在 messages 头部」的前缀缓存策略是否真的生效。
        """
        usage = getattr(response, "usage", None)
        if usage is None:
            return

        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)

        hit = getattr(usage, "prompt_cache_hit_tokens", None)
        if hit is None:
            details = getattr(usage, "prompt_tokens_details", None)
            if details is not None:
                hit = getattr(details, "cached_tokens", None)
        if hit is None:
            return

        hit = int(hit or 0)
        percent = (hit / prompt_tokens * 100) if prompt_tokens else 0.0
        logger.info(
            "[LLM缓存] %s | 命中 %d / 输入 %d (%.1f%%)",
            tag, hit, prompt_tokens, percent,
        )

    async def _chat(self, tag: str, **kwargs):
        """所有 LLM 请求的统一入口，自动附带缓存命中日志。"""
        response = await self.client.chat.completions.create(**kwargs)
        self._log_cache_usage(response, tag)
        return response

    # ------------------------------------------------------------------
    # 回复抽取：区分「真·空回复」与「工具调用回复」
    # ------------------------------------------------------------------
    def _extract_text(self, response, tag: str) -> str:
        """从响应中取出正文，并把空回复的原因写进日志。

        为什么需要单独一层：调用方普遍写成
            content = (response.choices[0].message.content or "").strip()
        一旦 content 是 None/空串，`or "当前没有可用回答。"` 就会把它兜住，
        界面只显示一句无信息量的文案，日志里却什么都没有 —— 线上极难定位。

        实际有三种互不相同的情况：
          1. 正常文本回复                     → 返回正文
          2. 模型返回了 tool_calls 而没给正文 → 本服务未实现工具执行，属配置问题
          3. 真的什么都没返回                 → 通常是拒答 / finish_reason=length
        """
        message = response.choices[0].message
        content = (message.content or "").strip()
        if content:
            return content

        choice = response.choices[0]
        tool_calls = getattr(message, "tool_calls", None)
        reasoning = (getattr(message, "reasoning_content", None) or "").strip()

        if tool_calls:
            logger.error(
                "[LLM空回复] %s | 模型返回了 %d 个 tool_calls 但没有正文，"
                "本服务未实现工具执行。请改用非 Agent 型模型（如 deepseek-chat）",
                tag, len(tool_calls),
            )
        elif reasoning:
            logger.error(
                "[LLM空回复] %s | 只返回了思维链（%d 字），正文为空，"
                "finish_reason=%s。通常是 max_tokens 不足",
                tag, len(reasoning), choice.finish_reason,
            )
        else:
            logger.error(
                "[LLM空回复] %s | 正文为空且无思维链，finish_reason=%s",
                tag, choice.finish_reason,
            )
        return ""

    async def analyze_rescue(
        self,
        transcript: str,
        material: str,
        preset_id: str | None = None,
        prompt_override: str | None = None,
    ) -> dict:
        """
        紧急救场分析
        - 根据课堂转录和课程资料，提取老师的问题并生成答案

        Args:
            transcript: 最近的课堂转录文本
            material: 课程 PPT 资料文本

        Returns:
            包含 context, question, answer 的字典
        """
        # 组装 Prompt
        fallback_system_prompt = """你是一个大学课堂助手。你的任务是根据课堂录音转录和课程资料，快速分析以下内容：
1. 目前课堂正在讲的内容概要（简短）
2. 老师刚才提出的问题是什么（精确提取）
3. 该问题的建议答案（结合课程资料给出准确、简洁的回答）

请用以下 JSON 格式回复（不要加 markdown 代码块标记）：
{
    "context": "课堂内容概要",
    "question": "老师提出的问题",
    "answer": "建议答案"
}"""
        system_prompt = self.prompt_service.get_prompt(
            category="rescue",
            fallback_prompt=fallback_system_prompt,
            preset_id=preset_id,
            prompt_override=prompt_override,
        )

        # 顺序说明：把整节课不变的「课程资料」放在最前、每次都变的「转录」放后面，
        # 使 system_prompt + 课程资料 构成稳定前缀，命中服务端 prompt 前缀缓存
        # （DeepSeek 命中价约为未命中的 1/10）。语义与原先一致，仅调整段落顺序。
        user_prompt = f"""【课程资料（PPT内容）】
{material if material else "暂无课程资料"}

【课堂录音转录（最近2分钟）】
{transcript}

请分析并提取问题和答案。"""

        try:
            response = await self._chat(
                "analyze_rescue",
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # 低温度，提高准确性
                max_tokens=1000,
            )

            # 解析 LLM 返回的 JSON
            content = response.choices[0].message.content.strip()

            # 尝试解析 JSON
            try:
                result = json.loads(content)
                return {
                    "context": result.get("context", "无法提取课堂内容"),
                    "question": result.get("question", "无法识别问题"),
                    "answer": result.get("answer", "无法生成答案")
                }
            except json.JSONDecodeError:
                # 如果 LLM 没有返回有效 JSON，直接返回原文
                return {
                    "context": "正在解析中...",
                    "question": "请查看课堂内容",
                    "answer": content
                }

        except Exception as e:
            return {
                "context": "LLM 调用失败",
                "question": str(e),
                "answer": "请检查 API 配置是否正确"
            }

    async def analyze_catchup(
        self,
        transcript: str,
        material: str,
        preset_id: str | None = None,
        prompt_override: str | None = None,
    ) -> dict:
        """
        课堂进度摘要 - 告知用户老师讲到哪了、有什么重要信息

        Args:
            transcript: 最近的课堂转录文本
            material: 课程 PPT 资料文本

        Returns:
            包含 summary 的字典
        """
        fallback_system_prompt = """你是一个大学课堂助手。学生正在上课但没有认真听，现在想知道老师讲到哪了。
请根据课堂录音转录和课程资料，简洁地总结：
1. 老师目前讲到了什么内容
2. 有没有重要的知识点、考试重点或需要注意的事项
3. 如果有布置作业或提到截止日期，也请标出

请用简洁易读的中文回复，不要太长，控制在200字以内。"""
        system_prompt = self.prompt_service.get_prompt(
            category="catchup",
            fallback_prompt=fallback_system_prompt,
            preset_id=preset_id,
            prompt_override=prompt_override,
        )

        user_prompt = f"""【课程资料（PPT内容）】
{material if material else "暂无课程资料"}

【课堂录音转录】
{transcript}

请总结老师讲到哪了。"""

        try:
            response = await self._chat(
                "analyze_catchup",
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500,
            )
            content = response.choices[0].message.content.strip()
            return {"summary": content}
        except Exception as e:
            return {"summary": f"LLM 调用失败: {str(e)}，请检查 API 配置"}

    async def answer_catchup_question(
        self,
        summary: str,
        transcript: str,
        material: str,
        question: str,
        history: list[dict] | None = None,
        preset_id: str | None = None,
        prompt_override: str | None = None,
    ) -> dict:
        """围绕当前课堂进度继续追问。"""
        safe_history = history or []
        history_text = "\n".join(
            f"{item.get('role', 'user')}: {item.get('content', '')}"
            for item in safe_history[-8:]
            if item.get('content')
        ) or "暂无历史追问"

        fallback_system_prompt = """你是一个课堂随堂答疑助手。你需要基于当前课堂进度摘要、最近课堂转录、课程资料以及已有追问历史，回答学生的后续问题。

要求：
1. 优先依据给定上下文回答，不要编造课堂里没提过的结论。
2. 回答要直接、清楚，适合学生边上课边看。
3. 如果问题是解释术语、公式或概念，可以补充必要背景，但不要长篇展开。
4. 如果上下文不足，要明确说明“当前课堂上下文不足”，再给出谨慎推断。"""
        system_prompt = self.prompt_service.get_prompt(
            category="catchup_chat",
            fallback_prompt=fallback_system_prompt,
            preset_id=preset_id,
            prompt_override=prompt_override,
        )

        user_prompt = f"""【课程资料】
{material if material else '暂无课程资料'}

【当前课堂进度摘要】
{summary}

【最近课堂转录】
{transcript}

【已有追问历史】
{history_text}

【学生的新问题】
{question}

请直接回答学生。"""

        try:
            response = await self._chat(
                "answer_catchup_question",
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=800,
            )
            content = self._extract_text(response, "answer_catchup_question")
            if not content:
                return {
                    "answer": "模型本次没有返回内容（已记录到后端日志）。"
                              "请再试一次；若持续如此，请在设置里更换模型。"
                }
            return {"answer": content}
        except Exception as exc:
            logger.exception("[LLM调用失败] answer_catchup_question")
            return {"answer": f"LLM 调用失败: {exc}，请检查 API 配置"}

    async def answer_rescue_question(
        self,
        context: str,
        extracted_question: str,
        suggested_answer: str,
        transcript: str,
        material: str,
        followup: str,
        history: list[dict] | None = None,
        preset_id: str | None = None,
        prompt_override: str | None = None,
    ) -> dict:
        """围绕救场结果继续追问。"""
        safe_history = history or []
        history_text = "\n".join(
            f"{item.get('role', 'user')}: {item.get('content', '')}"
            for item in safe_history[-8:]
            if item.get('content')
        ) or "暂无历史追问"

        fallback_system_prompt = """你是一个课堂救场辅助助手。你需要基于当前课堂上下文、识别到的老师问题、已有建议答案、最近课堂转录、课程资料以及追问历史，继续回答学生的后续问题。

要求：
1. 优先依据当前课堂上下文和已给出的救场答案作答，不要无依据扩展。
2. 回答要适合学生临场查看，简洁直接。
3. 如果上下文不足，要明确指出“当前课堂上下文不足”，再给出谨慎推断。
4. 如果学生是在追问如何表达，可以给出更口语化、更短的回答版本。"""
        system_prompt = self.prompt_service.get_prompt(
            category="rescue_chat",
            fallback_prompt=fallback_system_prompt,
            preset_id=preset_id,
            prompt_override=prompt_override,
        )

        user_prompt = f"""【课程资料】
{material if material else '暂无课程资料'}

【课堂上下文】
{context}

【识别到的老师问题】
{extracted_question}

【当前建议答案】
{suggested_answer}

【最近课堂转录】
{transcript}

【已有追问历史】
{history_text}

【学生的新问题】
{followup}

请直接回答学生。"""

        try:
            response = await self._chat(
                "answer_rescue_question",
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=800,
            )
            content = self._extract_text(response, "answer_rescue_question")
            if not content:
                return {
                    "answer": "模型本次没有返回内容（已记录到后端日志）。"
                              "请再试一次；若持续如此，请在设置里更换模型。"
                }
            return {"answer": content}
        except Exception as exc:
            logger.exception("[LLM调用失败] answer_rescue_question")
            return {"answer": f"LLM 调用失败: {exc}，请检查 API 配置"}

    async def generate_class_summary(self, transcript: str, material: str) -> str:
        """
        生成课后总结 Markdown 笔记

        Args:
            transcript: 完整的课堂转录文本
            material: 课程 PPT 资料文本

        Returns:
            Markdown 格式的课堂总结
        """
        system_prompt = """你是一个专业的课堂笔记整理助手。请根据课堂录音转录和课程资料，生成一份结构化的 Markdown 课堂笔记。

笔记应包含以下章节：
# 📚 课堂笔记

## 📝 课程概要
（简要描述本节课的主题和内容）

## 🔑 核心知识点
（列出本节课的重要知识点，用编号列表）

## 💡 老师重点强调
（老师特别强调或反复提到的内容）

## 📋 作业与任务
（如果提到了作业、小测、DDL 等，列出来）

## ❓ 课堂问答
（记录课上的提问和回答）

## 📌 补充说明
（其他值得注意的信息）

请确保笔记内容准确、条理清晰。"""

        user_prompt = f"""【课程资料（PPT内容）】
{material if material else "暂无课程资料"}

【完整课堂转录】
{transcript}

请生成课堂笔记。"""

        # 思考型模型（如 deepseek-v4-flash-0731）会先产出很长的思维链（reasoning_content），
        # 正文（content）在思维链之后。若 max_tokens 太小，思维链会把额度吃光，
        # 导致 content 为空字符串——这正是"0 KB 总结文件"的根因。
        # 默认 20000，并允许用 .env 里的 SUMMARY_MAX_TOKENS 覆盖（带上下界校验），
        # 每次调用重新读取，改完即生效、无需改代码。
        summary_max_tokens = resolve_summary_max_tokens()

        try:
            response = await self._chat(
                "generate_class_summary",
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                max_tokens=summary_max_tokens,
            )
        except Exception as e:
            # 网络/鉴权/额度等调用失败：直接抛出去，绝不伪造成一份"笔记"。
            raise RuntimeError(f"LLM 调用失败：{e}") from e

        # 注意：以下解析与校验必须放在 try/except 之外。
        # 之前把 raise 写在 try 内，会被下面自己的 except 吞掉，
        # 变成一行"总结生成失败"字符串返回，反而写出假笔记（有内容但全是报错）。
        choice = response.choices[0]
        message = choice.message
        content = (message.content or "").strip()

        # 关键防线：绝不允许把空内容当作成功返回，否则会写出 0 字节的总结文件。
        if not content:
            reasoning = (getattr(message, "reasoning_content", None) or "").strip()
            if reasoning:
                raise ValueError(
                    f"LLM 只返回了思维链（{len(reasoning)} 字）而没有正文，"
                    f"finish_reason={choice.finish_reason}。"
                    "通常是因为 max_tokens 不足：请换用非思考型模型"
                    "（如 deepseek-v4-pro）或调大 SUMMARY_MAX_TOKENS。"
                )
            raise ValueError(
                f"LLM 返回了空内容（finish_reason={choice.finish_reason}），"
                "请检查模型与 API 配置。"
            )

        return content

    async def compress_monitoring_progress(self, previous_summary: str, recent_lines: list[str]) -> str:
        """
        将历史摘要和新近课堂记录压缩为新的滚动摘要。

        Args:
            previous_summary: 上一次滚动摘要，首次为空字符串
            recent_lines: 本轮待压缩的课堂记录（建议 50 行）

        Returns:
            新的精简摘要文本
        """
        if not recent_lines:
            return previous_summary.strip()

        system_prompt = """你是一个课堂记录压缩助手。你的任务是把“历史摘要”和“最新课堂记录”合并成一份更短但信息完整的滚动摘要。

要求：
1. 保留课程主题、关键知识点、老师强调内容、作业/截止日期、课堂问答。
2. 删除口头重复、语气词、无信息量重复表述。
3. 输出精简中文，不要编造内容。
4. 控制在 300 到 500 字以内。
5. 直接输出摘要正文，不要加 markdown 标题、代码块或额外说明。"""

        previous_summary = previous_summary.strip() or "暂无历史摘要"
        new_content = "\n".join(recent_lines)
        user_prompt = f"""【历史摘要】
{previous_summary}

【最新课堂记录】
{new_content}

请输出新的滚动摘要。"""

        try:
            response = await self._chat(
                "compress_monitoring_progress",
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=900,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("LLM 未返回滚动摘要内容")
            return content
        except Exception:
            logger.exception("滚动摘要生成失败")
            raise
