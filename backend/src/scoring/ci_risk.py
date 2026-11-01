"""可解释的阶段先验 PoS + 事件情报风险分（非临床 LoA）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

from backend.src.core.logger import get_logger

logger = get_logger("scoring.ci_risk")

_PRIOR_PATH = Path(__file__).resolve().parents[3] / "config" / "phase_pos_priors.yaml"
_CACHE: Optional[Dict[str, Any]] = None


def _load_config() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not _PRIOR_PATH.exists():
        _CACHE = {
            "source": "fallback",
            "priors": {"unknown": 0.15},
            "story_type_weights": {"other": 0.4},
        }
        return _CACHE
    _CACHE = yaml.safe_load(_PRIOR_PATH.read_text(encoding="utf-8")) or {}
    return _CACHE


def stage_prior_pos(stage: Optional[str]) -> Dict[str, Any]:
    cfg = _load_config()
    priors = cfg.get("priors") or {}
    key = (stage or "unknown").strip().lower().replace(" ", "").replace("-", "")
    # 兼容 phase_1 / phase1
    aliases = {
        "phase_1": "phase1",
        "phase_2": "phase2",
        "phase_3": "phase3",
        "nda": "filed",
        "bla": "filed",
        "marketing": "approved",
        "launched": "approved",
    }
    key = aliases.get(key, key)
    value = float(priors.get(key, priors.get("unknown", 0.15)))
    return {
        "stage": stage,
        "stage_key": key,
        "prior_pos": value,
        "source": cfg.get("source"),
        "disclaimer": "阶段先验，非临床 LoA / DT&SR 预测模型",
        "components": {"stage_prior": value},
    }


def adjust_prior_with_signals(
    base: Dict[str, Any],
    *,
    competition_count: int = 0,
    safety_news: int = 0,
    deal_news: int = 0,
) -> Dict[str, Any]:
    prior = float(base.get("prior_pos") or 0.15)
    delta = 0.0
    if competition_count >= 8:
        delta -= 0.08
    elif competition_count >= 4:
        delta -= 0.04
    if safety_news > 0:
        delta -= min(0.10, 0.03 * safety_news)
    if deal_news > 0:
        delta += min(0.08, 0.02 * deal_news)
    adjusted = max(0.01, min(0.99, prior + delta))
    components = dict(base.get("components") or {})
    components.update(
        {
            "competition_delta": round(delta if competition_count else 0.0, 4)
            if competition_count
            else 0.0,
            "safety_delta": round(-min(0.10, 0.03 * safety_news), 4) if safety_news else 0.0,
            "deal_delta": round(min(0.08, 0.02 * deal_news), 4) if deal_news else 0.0,
            "adjusted_pos": adjusted,
        }
    )
    out = dict(base)
    out["prior_pos"] = prior
    out["adjusted_pos"] = adjusted
    out["components"] = components
    return out


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def compute_ci_risk_score(
    *,
    story_types: Sequence[str],
    news_count: int,
    recent_growth: float = 0.0,
    has_product: bool = False,
    has_org: bool = False,
    burst_prob: Optional[float] = None,
) -> Dict[str, Any]:
    cfg = _load_config()
    weights = cfg.get("story_type_weights") or {}
    type_w = 0.4
    if story_types:
        type_w = max(float(weights.get((t or "other").lower(), 0.4)) for t in story_types)

    volume = _clamp01(0.15 * min(int(news_count or 0), 6) + 0.4 * max(0.0, recent_growth))
    entity = 0.0
    if has_product:
        entity += 0.6
    if has_org:
        entity += 0.4
    entity = _clamp01(entity)

    if burst_prob is None:
        score = 0.40 * type_w + 0.35 * volume + 0.25 * entity
        burst_component = 0.0
        w_burst = 0.0
    else:
        bp = _clamp01(burst_prob)
        score = 0.35 * type_w + 0.25 * volume + 0.20 * entity + 0.20 * bp
        burst_component = bp
        w_burst = 0.20

    score = _clamp01(score)
    return {
        "ci_risk_score": round(score, 4),
        "burst_prob": None if burst_prob is None else round(burst_component, 4),
        "score_components": {
            "story_type_weight": round(type_w, 4),
            "volume_score": round(volume, 4),
            "entity_score": round(entity, 4),
            "burst_prob": burst_component if w_burst else None,
            "weights": {
                "story_type": 0.35 if w_burst else 0.40,
                "volume": 0.25 if w_burst else 0.35,
                "entity": 0.20 if w_burst else 0.25,
                "burst": w_burst,
            },
        },
        "disclaimer": "情报关注/风险评分，非药物临床成功概率",
    }
