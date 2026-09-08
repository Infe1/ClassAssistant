"""单线程交错录音探针：默认麦克风 + 立体声混音 RMS。配合外部 TTS 播放使用。"""
import array
import sys
import time

import pyaudio

DUR = 20
CHUNK = 1600


def rms(data: bytes) -> float:
    samples = array.array("h", data)
    if not samples:
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5 / 32768.0


def open_input(p: pyaudio.PyAudio, index: int | None, rate: int):
    for r in (rate, 48000, 44100):
        try:
            return p.open(
                format=pyaudio.paInt16, channels=1, rate=r, input=True,
                input_device_index=index, frames_per_buffer=CHUNK,
            ), r
        except Exception as exc:
            last = exc
    raise last


def main() -> None:
    p = pyaudio.PyAudio()
    default_idx = int(p.get_default_input_device_info()["index"])

    loop_idx = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        name = str(info.get("name", ""))
        if info.get("maxInputChannels", 0) > 0 and ("混音" in name or "Stereo" in name.lower()):
            loop_idx = i
            print(f"loopback candidate [{i}] {name}", flush=True)

    mic_stream, mic_rate = open_input(p, default_idx, 16000)
    print(f"default mic [{default_idx}] opened @{mic_rate}", flush=True)

    loop_stream = None
    if loop_idx is not None:
        try:
            loop_stream, loop_rate = open_input(p, loop_idx, 16000)
            print(f"stereo-mix [{loop_idx}] opened @{loop_rate}", flush=True)
        except Exception as exc:
            print(f"stereo-mix open failed: {exc}", flush=True)

    print(f"recording {DUR}s ... play TTS NOW", flush=True)
    mic_peak = mic_sum = mic_n = 0.0
    loop_peak = loop_sum = loop_n = 0.0
    start = time.time()
    while time.time() - start < DUR:
        data = mic_stream.read(CHUNK, exception_on_overflow=False)
        r = rms(data)
        mic_peak = max(mic_peak, r)
        mic_sum += r
        mic_n += 1
        if loop_stream is not None:
            data = loop_stream.read(CHUNK, exception_on_overflow=False)
            r = rms(data)
            loop_peak = max(loop_peak, r)
            loop_sum += r
            loop_n += 1

    mic_stream.stop_stream()
    mic_stream.close()
    if loop_stream is not None:
        loop_stream.stop_stream()
        loop_stream.close()
    p.terminate()

    print(f"default-mic: avg={mic_sum / max(mic_n, 1):.5f} peak={mic_peak:.5f}", flush=True)
    if loop_n:
        print(f"stereo-mix:  avg={loop_sum / loop_n:.5f} peak={loop_peak:.5f}", flush=True)


if __name__ == "__main__":
    main()
