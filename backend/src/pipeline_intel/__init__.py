"""研发管线：抓取 → 视觉抽取 → 对账入库 → 通知。"""

from backend.src.core.config import vision_readiness
from backend.src.pipeline_intel.service import run_pipeline_sync

__all__ = ["run_pipeline_sync", "vision_readiness"]