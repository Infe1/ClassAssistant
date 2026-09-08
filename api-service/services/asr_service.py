"""
ASR 语音识别服务（Slim 版）
==========================
只保留两条识别链路：
    - webspeech: 前端 WebView2 / 浏览器 Web Speech 识别（微软在线服务，免 key）
                 本模块仅提供占位实现，真实文本由前端经 /ingest_asr_text 注入
    - sherpa:    本地流式识别 sherpa-onnx（streaming Zipformer，纯 CPU 推理，免联网）
    - mock:      空实现，用于开发测试
"""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import pyaudio
from dotenv import load_dotenv

from config import MODELS_DIR

load_dotenv()

logger = logging.getLogger(__name__)

# ---- 音频录制参数 ----
SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
CHANNELS = int(os.getenv("AUDIO_CHANNELS", "1"))
CHUNK_SIZE = int(os.getenv("AUDIO_CHUNK_SIZE", "3200"))  # 100ms @16kHz, 16bit, mono


class BaseASR:
    """ASR 基类，定义统一接口"""

    def __init__(self, on_text: Callable[[str, bool], None]):
        """
        Args:
            on_text: 回调函数 (text, is_final)
                     text - 识别到的文本
                     is_final - 是否为一句话的最终结果
        """
        self.on_text = on_text
        self._running = False

    def start(self):
        """启动 ASR 识别"""
        raise NotImplementedError

    def stop(self):
        """停止 ASR 识别"""
        raise NotImplementedError


class MockASR(BaseASR):
    """Mock ASR - 不进行真实录音/识别，仅用于测试"""

    def start(self):
        self._running = True
        logger.info("[MockASR] started (no real recognition)")

    def stop(self):
        self._running = False
        logger.info("[MockASR] stopped")


# =====================================================================
# 浏览器 Web Speech 识别占位实现
# =====================================================================

class BrowserSpeechASR(BaseASR):
    """
    浏览器端 Web Speech 识别占位实现。

    说明：
    - 该模式本身不采集音频，只是让监控服务保持启用状态。
    - 真正的识别文本由前端通过 /ingest_asr_text 注入。
    """

    def start(self):
        self._running = True
        logger.info("[BrowserSpeechASR] started (frontend will inject text)")

    def stop(self):
        self._running = False
        logger.info("[BrowserSpeechASR] stopped")


# =====================================================================
# sherpa-onnx 本地流式识别实现（streaming Zipformer, CPU）
# =====================================================================

class SherpaOnnxASR(BaseASR):
    """
    基于 sherpa-onnx 的本地流式语音识别。

    - 使用 streaming Zipformer transducer 模型，纯 CPU 推理，无需联网。
    - 模型目录解析顺序：SHERPA_MODEL_DIR > MODELS_DIR/<SHERPA_MODEL_NAME>
    - 通过 sherpa 内置端点检测断句：说完一句话（默认 2.4s 静音）回调 is_final=True，
      说话过程中的中间结果回调 is_final=False。
    - 可用 SHERPA_INPUT_DEVICE 指定输入设备索引（如立体声混音），缺省用系统默认麦克风。
    """

    def __init__(self, on_text: Callable[[str, bool], None]):
        super().__init__(on_text)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._mic: Optional[pyaudio.PyAudio] = None
        self._stream = None

    @staticmethod
    def _resolve_model_dir() -> Path:
        env_dir = os.getenv("SHERPA_MODEL_DIR", "").strip()
        if env_dir:
            return Path(env_dir)

        model_name = os.getenv(
            "SHERPA_MODEL_NAME",
            "sherpa-onnx-streaming-zipformer-small-bilingual-zh-en-2023-02-16",
        ).strip()
        return Path(MODELS_DIR) / model_name

    @staticmethod
    def _find_model_files(model_dir: Path) -> dict[str, Path]:
        """在模型目录中定位 tokens / encoder / decoder / joiner 文件。"""
        if not model_dir.is_dir():
            raise RuntimeError(
                f"sherpa 模型目录不存在: {model_dir}。"
                "请设置 SHERPA_MODEL_DIR，或将模型放到 models/ 下"
            )

        files: dict[str, Path] = {}

        tokens = model_dir / "tokens.txt"
        if not tokens.exists():
            raise RuntimeError(f"缺少 tokens.txt: {model_dir}")
        files["tokens"] = tokens

        def pick(prefix: str) -> Path:
            candidates = sorted(model_dir.glob(f"{prefix}*.onnx"))
            if not candidates:
                raise RuntimeError(f"模型目录缺少 {prefix}*.onnx: {model_dir}")
            # 优先 int8 量化版本（体积小、CPU 上更快）
            int8 = [p for p in candidates if "int8" in p.name]
            return (int8 or candidates)[0]

        files["encoder"] = pick("encoder")
        files["decoder"] = pick("decoder")
        files["joiner"] = pick("joiner")
        return files

    @staticmethod
    def _resolve_input_device(mic: "pyaudio.PyAudio") -> int | None:
        """解析输入设备索引；未配置 SHERPA_INPUT_DEVICE 时用系统默认。"""
        raw = os.getenv("SHERPA_INPUT_DEVICE", "").strip()
        if raw == "":
            return None
        try:
            index = int(raw)
        except ValueError:
            logger.warning("[SherpaASR] 非法的 SHERPA_INPUT_DEVICE=%r，使用默认设备", raw)
            return None

        info = mic.get_device_info_by_index(index)
        if info.get("maxInputChannels", 0) <= 0:
            raise RuntimeError(f"设备 {index} ({info.get('name')}) 不是输入设备")
        logger.info("[SherpaASR] using input device [%d] %s", index, info.get("name"))
        return index

    def start(self):
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise RuntimeError(f"sherpa_onnx 未安装: {exc}") from exc

        model_dir = self._resolve_model_dir()
        files = self._find_model_files(model_dir)

        num_threads = int(os.getenv("SHERPA_NUM_THREADS", "2"))
        rule1 = float(os.getenv("SHERPA_RULE1_SILENCE", "2.4"))

        logger.info(
            "[SherpaASR] loading model from %s (threads=%d, encoder=%s)",
            model_dir, num_threads, files["encoder"].name,
        )
        try:
            recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                tokens=str(files["tokens"]),
                encoder=str(files["encoder"]),
                decoder=str(files["decoder"]),
                joiner=str(files["joiner"]),
                num_threads=num_threads,
                sample_rate=SAMPLE_RATE,
                feature_dim=80,
                enable_endpoint_detection=True,
                rule1_min_trailing_silence=rule1,
                rule2_min_trailing_silence=1.2,
                rule3_min_utterance_length=20.0,
            )
        except Exception as exc:
            raise RuntimeError(f"sherpa 模型加载失败: {exc}") from exc

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, args=(recognizer,), daemon=True
        )
        self._thread.start()
        logger.info("[SherpaASR] started")

    def _run(self, recognizer):
        """工作线程：开麦 → 循环喂音频 → 解码 → 按端点回调"""
        try:
            self._mic = pyaudio.PyAudio()
            device_index = self._resolve_input_device(self._mic)
            self._stream = self._mic.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE,
            )
        except Exception as exc:
            logger.exception("[SherpaASR] microphone open failed")
            self.on_error(f"麦克风打开失败: {exc}")
            return

        import array

        stream = recognizer.create_stream()
        last_partial = ""
        last_log = 0.0

        try:
            while not self._stop_event.is_set():
                data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)

                pcm = array.array("h", data)
                samples = [sample / 32768.0 for sample in pcm]
                stream.accept_waveform(SAMPLE_RATE, samples)

                while recognizer.is_ready(stream):
                    recognizer.decode_stream(stream)

                text = recognizer.get_result(stream).strip()

                if recognizer.is_endpoint(stream):
                    if text:
                        self.on_text(text, True)
                    recognizer.reset(stream)
                    last_partial = ""
                elif text and text != last_partial:
                    last_partial = text
                    self.on_text(text, False)

                now = time.time()
                if last_partial and now - last_log > 5.0:
                    last_log = now
                    logger.info("[SherpaASR] partial: %s", last_partial[:60])
        except Exception:
            logger.exception("[SherpaASR] audio loop error")
            self.on_error("本地识别循环异常，请查看后端日志")
        finally:
            self._close_audio()

    def on_error(self, message: str):
        """把致命错误转成一句 final 文本注入监控，让前端能感知到。"""
        try:
            self.on_text(message, True)
        except Exception:
            logger.exception("[SherpaASR] error notify failed")

    def _close_audio(self):
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._mic:
            try:
                self._mic.terminate()
            except Exception:
                pass
            self._mic = None

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._close_audio()
        logger.info("[SherpaASR] stopped")


# =====================================================================
# 工厂函数
# =====================================================================

def create_asr(on_text: Callable[[str, bool], None], asr_model: str | None = None) -> BaseASR:
    """
    根据 ASR_MODE 环境变量创建对应的 ASR 实例

    Args:
        on_text: 文本回调 (text, is_final)
        asr_model: 保留参数位，当前未使用

    Returns:
        BaseASR 子类实例
    """
    mode = os.getenv("ASR_MODE", "webspeech").lower().strip()
    logger.info("[ASR] mode=%s", mode)
    if mode in {"webspeech", "edge-webspeech", "browser"}:
        return BrowserSpeechASR(on_text)
    elif mode in {"sherpa", "sherpa-onnx", "local"}:
        return SherpaOnnxASR(on_text)
    elif mode == "mock":
        return MockASR(on_text)
    else:
        logger.warning("[ASR] unknown mode %r, fallback to webspeech", mode)
        return BrowserSpeechASR(on_text)
