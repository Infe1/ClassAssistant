"""
partial 实时字幕管线自测
========================
用法: .venv/Scripts/python scripts/test_ws_pipeline.py [port]
流程: 连 WS → start_monitor(webspeech) → 注入 partial/final 文本 → 校验 WS 收到
      transcript_partial 广播、final 落盘 → stop_monitor
"""

import asyncio
import json
import sys
import urllib.request

import websockets

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
BASE = f"http://127.0.0.1:{PORT}/api"


def post(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def main() -> None:
    results: dict[str, bool] = {}
    received: list[dict] = []

    async with websockets.connect(f"ws://127.0.0.1:{PORT}/api/ws/alerts") as ws:
        start = post("start_monitor", {"course_name": "WS管线自测"})
        results["start_monitor ok"] = start.get("status") == "started"
        print("start_monitor:", start)

        # 模拟前端 webspeech 注入：partial 逐渐增长 → final
        partials = ["今天我们", "今天我们讲", "今天我们讲一下二分查找"]
        for p in partials:
            post("ingest_asr_text", {"text": p, "is_final": False})
            await asyncio.sleep(0.3)
        post("ingest_asr_text", {"text": "今天我们讲一下二分查找的时间复杂度", "is_final": True})
        await asyncio.sleep(1.0)

        # 收集 WS 消息（期间可能有 pong 等）
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                try:
                    received.append(json.loads(msg))
                except json.JSONDecodeError:
                    continue
        except asyncio.TimeoutError:
            pass

        partials_ws = [m for m in received if m.get("type") == "transcript_partial"]
        texts = [m.get("text", "") for m in partials_ws]
        results["partial 广播收到"] = len(texts) >= 2
        results["partial 内容正确"] = any("二分查找" in t for t in texts)
        results["final 后清空 partial"] = texts and texts[-1] == ""

        stop = post("stop_monitor")
        results["stop_monitor ok"] = stop.get("status") == "stopped"
        print("stop_monitor:", stop.get("status"))

    print("-" * 50)
    print("WS 收到的消息类型:", [m.get("type") for m in received])
    print("partial 文本序列:", texts)
    print("-" * 50)
    ok = all(results.values())
    for k, v in results.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print("RESULT:", "ALL PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
