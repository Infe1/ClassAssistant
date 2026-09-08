"""
sherpa-onnx 流式识别自测脚本
============================
用法: .venv/Scripts/python scripts/test_sherpa.py [模型目录]
验证:
  1. 模型能否加载（int8）
  2. 测试 WAV 识别文本是否正确
  3. 流式喂入（100ms/块）时的 RTF（实时率）与 partial 输出
"""

import array
import sys
import time
import wave
from pathlib import Path

import sherpa_onnx

DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "models" / (
    "sherpa-onnx-streaming-zipformer-small-bilingual-zh-en-2023-02-16"
)


def load_model(model_dir: Path, num_threads: int = 2) -> sherpa_onnx.OnlineRecognizer:
    def pick(prefix: str) -> Path:
        candidates = sorted(model_dir.glob(f"{prefix}*.onnx"))
        int8 = [p for p in candidates if "int8" in p.name]
        return (int8 or candidates)[0]

    return sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=str(model_dir / "tokens.txt"),
        encoder=str(pick("encoder")),
        decoder=str(pick("decoder")),
        joiner=str(pick("joiner")),
        num_threads=num_threads,
        sample_rate=16000,
        feature_dim=80,
        enable_endpoint_detection=True,
        rule1_min_trailing_silence=2.4,
        rule2_min_trailing_silence=1.2,
        rule3_min_utterance_length=20.0,
    )


def read_wav(path: Path) -> tuple[int, list[float]]:
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())
    pcm = array.array("h", frames)
    if w.getnchannels() > 1:
        pcm = array.array("h", pcm[:: w.getnchannels()])
    return rate, [s / 32768.0 for s in pcm]


def main() -> None:
    recognizer = None
    if len(sys.argv) > 1 and sys.argv[1].lower().endswith(".wav"):
        # 单文件模式: scripts/test_sherpa.py some.wav
        wav_path = Path(sys.argv[1])
        rate, samples = read_wav(wav_path)
        duration = len(samples) / rate
        recognizer = load_model(DEFAULT_MODEL)

        stream = recognizer.create_stream()
        t_start = time.perf_counter()
        finals: list[str] = []
        last_partial = ""
        chunk = int(rate * 0.1)
        for i in range(0, len(samples), chunk):
            stream.accept_waveform(rate, samples[i : i + chunk])
            while recognizer.is_ready(stream):
                recognizer.decode_stream(stream)
            text = recognizer.get_result(stream).strip()
            offset = i / rate
            if recognizer.is_endpoint(stream):
                if text:
                    finals.append(text)
                    print(f"  [{offset:6.1f}s] FINAL: {text}")
                recognizer.reset(stream)
                last_partial = ""
            elif text and text != last_partial:
                last_partial = text
                print(f"  [{offset:6.1f}s] partial: {text}")

        # 统计 WAV 本身的响度
        seg_rms = (sum(s * s for s in samples[::10]) / (len(samples) // 10 + 1)) ** 0.5 / 32768.0
        print(f"  wav RMS={seg_rms:.4f}")

        elapsed = time.perf_counter() - t_start
        rtf = elapsed / duration if duration else 0
        print(f"{wav_path.name}: {duration:.1f}s audio, decode {elapsed * 1000:.0f} ms, RTF={rtf:.3f}")
        print(f"finals: {finals}")
        return

    model_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MODEL
    print(f"model dir: {model_dir}")

    t0 = time.perf_counter()
    recognizer = load_model(model_dir)
    print(f"model loaded in {time.perf_counter() - t0:.2f}s")

    wavs = sorted((model_dir / "test_wavs").glob("*.wav"))
    if not wavs:
        print("no test wavs found")
        return

    for wav_path in wavs:
        rate, samples = read_wav(wav_path)
        duration = len(samples) / rate

        # ---- 流式喂入：100ms/块，模拟真实麦克风路径 ----
        stream = recognizer.create_stream()
        t_start = time.perf_counter()
        finals: list[str] = []
        last_partial = ""
        partial_updates = 0
        chunk = int(rate * 0.1)

        for i in range(0, len(samples), chunk):
            stream.accept_waveform(rate, samples[i : i + chunk])
            while recognizer.is_ready(stream):
                recognizer.decode_stream(stream)

            text = recognizer.get_result(stream).strip()
            if recognizer.is_endpoint(stream):
                if text:
                    finals.append(text)
                recognizer.reset(stream)
                last_partial = ""
            elif text and text != last_partial:
                last_partial = text
                partial_updates += 1

        elapsed = time.perf_counter() - t_start
        rtf = elapsed / duration if duration else 0

        print("-" * 60)
        print(f"{wav_path.name}: {duration:.1f}s audio, decode {elapsed * 1000:.0f} ms, RTF={rtf:.3f}")
        print(f"  partial updates: {partial_updates}")
        print(f"  finals: {finals}")

    print("=" * 60)
    print("RTF 解读: <1 即快于实时；0.03 表示每秒音频耗 30ms CPU 时间")


if __name__ == "__main__":
    main()
