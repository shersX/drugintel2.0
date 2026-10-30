#!/usr/bin/env python3
"""管线视觉模型冒烟：对一张快照计时调用，看要多久。

用法（项目根目录）:
  .venv/Scripts/python scripts/smoke_pipeline_vision.py
  .venv/Scripts/python scripts/smoke_pipeline_vision.py data/pipeline_snapshots/20261030/b0f27fc126f43838.png
  .venv/Scripts/python scripts/smoke_pipeline_vision.py --timeout 600 --retries 1
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _default_image() -> Path:
    snap_root = PROJECT_ROOT / "data" / "pipeline_snapshots"
    preferred = snap_root / "20261030" / "b0f27fc126f43838.png"
    if preferred.is_file():
        return preferred
    if not snap_root.is_dir():
        raise SystemExit(f"未找到快照目录: {snap_root}")
    pngs = sorted(snap_root.rglob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pngs:
        raise SystemExit(f"未找到管线快照 PNG: {snap_root}")
    return pngs[0]


async def _run(image: Path, *, timeout_sec: float, retries: int) -> int:
    from backend.src.core.config import VisionEnvConfig, vision_readiness
    from backend.src.llm.client import SiliconFlowClient
    from backend.src.pipeline_intel.extract import extract_from_images

    ready = vision_readiness()
    if not ready.get("ready"):
        print(ready.get("message") or "视觉模型未就绪")
        return 2

    cfg = VisionEnvConfig.load()
    size_kb = image.stat().st_size / 1024
    print(f"图片: {image.relative_to(PROJECT_ROOT)}  ({size_kb:.1f} KB)")
    print(f"模型: {cfg.model}")
    print(f"地址: {cfg.base_url}")
    print(f"超时: {timeout_sec:.0f}s  重试: {retries}")
    print("--- 开始调用 ---")

    client = SiliconFlowClient(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model,
        timeout_sec=timeout_sec,
        max_retries=retries,
    )

    t0 = time.perf_counter()
    try:
        result = await extract_from_images(
            [str(image)],
            client=client,
            model_name=cfg.model,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        print(f"失败 ({type(exc).__name__}): {exc or repr(exc)}")
        print(f"耗时: {elapsed:.1f}s")
        return 1

    elapsed = time.perf_counter() - t0
    assets = result.get("assets") or []
    deals = result.get("deals") or []
    raw = result.get("raw_text") or ""
    print(f"成功")
    print(f"耗时: {elapsed:.1f}s")
    print(f"assets: {len(assets)}  deals: {len(deals)}  raw_chars: {len(raw)}")
    if assets:
        sample = assets[0]
        name = sample.get("drug_name") or sample.get("generic_name") or "(unnamed)"
        print(f"首条样例: {name} / {sample.get('stage') or '-'} / {sample.get('target') or '-'}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="管线视觉模型耗时冒烟测试")
    parser.add_argument(
        "image",
        nargs="?",
        type=Path,
        help="管线快照图片路径（默认用最新或今日那张）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="单次请求超时秒数（默认 600，便于测真实耗时）",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="最大尝试次数（默认 1，冒烟只测一轮）",
    )
    args = parser.parse_args()
    image = (args.image or _default_image()).resolve()
    if not image.is_file():
        raise SystemExit(f"图片不存在: {image}")

    code = asyncio.run(_run(image, timeout_sec=args.timeout, retries=max(1, args.retries)))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
