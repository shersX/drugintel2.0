"""实体别名智能合并：共现/形态/嵌入召回 → 规则门 + LLM 裁判 → 自动或待审。"""

from __future__ import annotations

import asyncio
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.logger import get_logger
from backend.src.db.crud.news import news_ready_filter
from backend.src.entities.lexicon import ENTITY_TYPES, merge_entities
from backend.src.entities.normalize import preprocess
from backend.src.llm.client import SiliconFlowClient
from backend.src.models.entity_lexicon import EntityLexicon, EntityMergeCandidate
from backend.src.models.news import News

logger = get_logger("entities.alias_resolve")

_ROOT = Path(__file__).resolve().parents[3]
_JUDGE_PROMPT = _ROOT / "config" / "prompts" / "entity_alias_judge.txt"

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")

# LLM confidence 工程默认档（非向量阈值）
_AUTO_THRESH = {
    "product": 0.92,
    "drug": 0.92,
    "org": 0.85,
    "target": 0.85,
    "indication": 0.85,
}
_REVIEW_FLOOR = 0.70
_EMBED_RECALL = 0.55
_DEFAULT_LIMIT = 50
_NEWS_SCAN = 400
_COOCCUR_AUTO_ORG = 2


def _run_coro(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=180)


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _is_latinish(text: str) -> bool:
    s = text or ""
    return bool(_LATIN_RE.search(s)) and not _has_cjk(s)


def _cjk_latin_pair(a: str, b: str) -> bool:
    return (_has_cjk(a) and _is_latinish(b)) or (_has_cjk(b) and _is_latinish(a))


def _ordered_ids(a: int, b: int) -> Tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _cosine(u: Sequence[float], v: Sequence[float]) -> float:
    if not u or not v or len(u) != len(v):
        return 0.0
    dot = sum(float(x) * float(y) for x, y in zip(u, v))
    nu = math.sqrt(sum(float(x) * float(x) for x in u))
    nv = math.sqrt(sum(float(y) * float(y) for y in v))
    if nu <= 0 or nv <= 0:
        return 0.0
    return float(dot / (nu * nv))


def _read_prompt() -> str:
    if not _JUDGE_PROMPT.exists():
        raise FileNotFoundError(f"缺少 prompt: {_JUDGE_PROMPT}")
    return _JUDGE_PROMPT.read_text(encoding="utf-8").strip()


def _parse_json(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


def _entity_names(row: EntityLexicon) -> Set[str]:
    out = {preprocess(row.canonical)}
    for a in row.aliases or []:
        p = preprocess(a)
        if p:
            out.add(p)
    return {x for x in out if x}


def _load_lexicon_map(session: Session) -> Dict[str, List[EntityLexicon]]:
    rows = list(
        session.scalars(
            select(EntityLexicon).where(
                EntityLexicon.status.in_(["active", "pending"])
            )
        ).all()
    )
    by_type: Dict[str, List[EntityLexicon]] = {t: [] for t in ENTITY_TYPES}
    for row in rows:
        et = (row.entity_type or "").strip().lower()
        if et in by_type:
            by_type[et].append(row)
    return by_type


def _find_rows_for_raw(
    rows: Sequence[EntityLexicon], raw: str
) -> List[EntityLexicon]:
    key = preprocess(raw)
    if not key:
        return []
    hits = []
    for row in rows:
        if key in _entity_names(row):
            hits.append(row)
    return hits


def _existing_decided_pairs(session: Session) -> Set[Tuple[int, int]]:
    """已 rejected / auto / accepted 的对不再重复推荐；pending 可更新分数。"""
    rows = session.scalars(
        select(EntityMergeCandidate).where(
            EntityMergeCandidate.status.in_(["rejected", "auto", "accepted"])
        )
    ).all()
    return {_ordered_ids(r.left_id, r.right_id) for r in rows}


def collect_cooccurrence_pairs(
    session: Session,
    by_type: Dict[str, List[EntityLexicon]],
    *,
    news_limit: int = _NEWS_SCAN,
) -> Dict[Tuple[str, int, int], Dict[str, Any]]:
    """同文 entity_raw 共现 → 候选信号。"""
    news_rows = list(
        session.scalars(
            select(News)
            .where(news_ready_filter())
            .where(News.entity_raw.isnot(None))
            .order_by(News.id.desc())
            .limit(news_limit)
        ).all()
    )
    bag: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
    type_keys = (
        ("product", "products"),
        ("drug", "drugs"),
        ("org", "orgs"),
        ("target", "targets"),
        ("indication", "indications"),
    )
    for news in news_rows:
        raw = news.entity_raw if isinstance(news.entity_raw, dict) else {}
        title = (news.title or "")[:120]
        for et, key in type_keys:
            names = [str(x) for x in (raw.get(key) or []) if str(x or "").strip()]
            if len(names) < 2:
                continue
            matched: List[EntityLexicon] = []
            seen_ids: Set[int] = set()
            for name in names:
                for row in _find_rows_for_raw(by_type.get(et) or [], name):
                    if row.id not in seen_ids:
                        seen_ids.add(row.id)
                        matched.append(row)
            if len(matched) < 2:
                continue
            for i in range(len(matched)):
                for j in range(i + 1, len(matched)):
                    a, b = matched[i], matched[j]
                    left, right = _ordered_ids(a.id, b.id)
                    pk = (et, left, right)
                    sig = bag.setdefault(
                        pk,
                        {
                            "cooccur": 0,
                            "titles": [],
                            "cjk_latin": _cjk_latin_pair(a.canonical, b.canonical),
                            "source": "cooccur",
                        },
                    )
                    sig["cooccur"] = int(sig["cooccur"]) + 1
                    if title and title not in sig["titles"] and len(sig["titles"]) < 5:
                        sig["titles"].append(title)
    return bag


def collect_morphology_pairs(
    by_type: Dict[str, List[EntityLexicon]],
) -> Dict[Tuple[str, int, int], Dict[str, Any]]:
    """CJK ↔ Latin 形态粗筛：优先 pending↔active，避免 active 全笛卡尔积。"""
    bag: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
    for et, rows in by_type.items():
        pending = [r for r in rows if r.status == "pending"]
        active = [r for r in rows if r.status == "active"]
        # 冷启动：至少一侧 pending；各侧按 seen 截断
        pending = sorted(pending, key=lambda r: int(r.seen_count or 0), reverse=True)[:30]
        pool = sorted(
            active + [r for r in rows if r.status == "pending"],
            key=lambda r: int(r.seen_count or 0),
            reverse=True,
        )[:50]
        for a in pending:
            for b in pool:
                if a.id == b.id:
                    continue
                if not _cjk_latin_pair(a.canonical, b.canonical):
                    continue
                left, right = _ordered_ids(a.id, b.id)
                bag[(et, left, right)] = {
                    "cooccur": 0,
                    "titles": [],
                    "cjk_latin": True,
                    "source": "morphology",
                }
    return bag


async def _embed_names(texts: List[str]) -> List[List[float]]:
    from backend.src.processors.embedding import SiliconFlowEmbeddingClient

    if not texts:
        return []
    client = SiliconFlowEmbeddingClient.from_env()
    # 分批
    out: List[List[float]] = []
    batch = 32
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        vecs = await client.embed(chunk)
        out.extend(vecs)
    return out


def collect_embedding_pairs(
    by_type: Dict[str, List[EntityLexicon]],
    *,
    top_k: int = 5,
) -> Dict[Tuple[str, int, int], Dict[str, Any]]:
    """多语嵌入近邻召回；失败则空。"""
    bag: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
    try:
        for et, rows in by_type.items():
            if len(rows) < 2:
                continue
            # 控制规模
            rows = sorted(rows, key=lambda r: int(r.seen_count or 0), reverse=True)[:80]
            texts = [r.canonical for r in rows]
            vecs = _run_coro(_embed_names(texts))
            if len(vecs) != len(rows):
                continue
            for i, row_i in enumerate(rows):
                scored: List[Tuple[float, EntityLexicon]] = []
                for j, row_j in enumerate(rows):
                    if i >= j:
                        continue
                    sim = _cosine(vecs[i], vecs[j])
                    if sim >= _EMBED_RECALL:
                        scored.append((sim, row_j))
                scored.sort(key=lambda x: x[0], reverse=True)
                for sim, row_j in scored[:top_k]:
                    left, right = _ordered_ids(row_i.id, row_j.id)
                    bag[(et, left, right)] = {
                        "cooccur": 0,
                        "titles": [],
                        "cjk_latin": _cjk_latin_pair(row_i.canonical, row_j.canonical),
                        "embed_sim": round(sim, 4),
                        "source": "embedding",
                    }
    except Exception as exc:
        logger.warning("实体嵌入召回跳过: %s", exc)
    return bag


def _merge_signal_bags(
    *bags: Dict[Tuple[str, int, int], Dict[str, Any]],
) -> Dict[Tuple[str, int, int], Dict[str, Any]]:
    out: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
    for bag in bags:
        for key, sig in bag.items():
            cur = out.get(key)
            if cur is None:
                out[key] = dict(sig)
                out[key]["sources"] = [sig.get("source") or "unknown"]
                continue
            cur["cooccur"] = max(int(cur.get("cooccur") or 0), int(sig.get("cooccur") or 0))
            if sig.get("cooccur"):
                # 累加共现更合理
                if "cooccur" in sig and sig.get("source") == "cooccur":
                    # 已在 collect 里累加；跨 bag 取 max 即可
                    pass
            titles = list(cur.get("titles") or [])
            for t in sig.get("titles") or []:
                if t not in titles and len(titles) < 5:
                    titles.append(t)
            cur["titles"] = titles
            cur["cjk_latin"] = bool(cur.get("cjk_latin") or sig.get("cjk_latin"))
            if sig.get("embed_sim") is not None:
                prev = cur.get("embed_sim")
                cur["embed_sim"] = max(float(prev or 0), float(sig["embed_sim"]))
            srcs = list(cur.get("sources") or [])
            s = sig.get("source")
            if s and s not in srcs:
                srcs.append(s)
            cur["sources"] = srcs
    return out


def _pick_keep_drop(
    left: EntityLexicon, right: EntityLexicon, preferred_canonical: str = ""
) -> Tuple[EntityLexicon, EntityLexicon]:
    pref = preprocess(preferred_canonical)
    if pref:
        if preprocess(left.canonical) == pref:
            return left, right
        if preprocess(right.canonical) == pref:
            return right, left
    # active 优先；aliases 多优先；seen 高优先；id 小优先
    def rank(r: EntityLexicon) -> Tuple:
        return (
            1 if r.status == "active" else 0,
            len(r.aliases or []),
            int(r.seen_count or 0),
            -r.id,
        )

    if rank(left) >= rank(right):
        return left, right
    return right, left


async def _llm_judge(
    *,
    entity_type: str,
    left: EntityLexicon,
    right: EntityLexicon,
    signals: Dict[str, Any],
) -> Dict[str, Any]:
    client = SiliconFlowClient.from_analyst_env()
    system = _read_prompt()
    user = json.dumps(
        {
            "entity_type": entity_type,
            "left": {
                "id": left.id,
                "canonical": left.canonical,
                "aliases": left.aliases or [],
                "status": left.status,
            },
            "right": {
                "id": right.id,
                "canonical": right.canonical,
                "aliases": right.aliases or [],
                "status": right.status,
            },
            "signals": {
                "cooccur": signals.get("cooccur"),
                "cjk_latin": signals.get("cjk_latin"),
                "embed_sim_reference_only": signals.get("embed_sim"),
                "titles": signals.get("titles") or [],
            },
        },
        ensure_ascii=False,
    )
    content = await client.chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        enable_thinking=False,
    )
    data = _parse_json(str(content or ""))
    same = bool(data.get("same_entity"))
    try:
        conf = float(data.get("confidence") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    return {
        "same_entity": same,
        "confidence": conf,
        "preferred_canonical": str(data.get("preferred_canonical") or ""),
        "reason": str(data.get("reason") or "")[:800],
    }


def _upsert_candidate(
    session: Session,
    *,
    entity_type: str,
    left_id: int,
    right_id: int,
    score: float,
    signals: Dict[str, Any],
    llm_reason: Optional[str],
    preferred_keep_id: Optional[int],
    status: str,
) -> EntityMergeCandidate:
    left_id, right_id = _ordered_ids(left_id, right_id)
    row = session.scalar(
        select(EntityMergeCandidate).where(
            EntityMergeCandidate.left_id == left_id,
            EntityMergeCandidate.right_id == right_id,
        )
    )
    if row is None:
        row = EntityMergeCandidate(
            entity_type=entity_type,
            left_id=left_id,
            right_id=right_id,
            score=score,
            signals=signals,
            llm_reason=llm_reason,
            preferred_keep_id=preferred_keep_id,
            status=status,
        )
        session.add(row)
    else:
        # 已终态不覆盖
        if row.status in ("rejected", "auto", "accepted"):
            return row
        row.score = score
        row.signals = signals
        row.llm_reason = llm_reason
        row.preferred_keep_id = preferred_keep_id
        row.status = status
        row.entity_type = entity_type
    session.flush()
    return row


def _rule_fast_reject(
    left: EntityLexicon, right: EntityLexicon, signals: Dict[str, Any]
) -> Optional[str]:
    if left.entity_type != right.entity_type:
        return "不同类型"
    if left.id == right.id:
        return "同一实体"
    # 无共现且无嵌入召回且非明确 CJK-Latin → 形态-only 仍允许进 LLM，但纯噪声砍掉
    if (
        int(signals.get("cooccur") or 0) <= 0
        and signals.get("embed_sim") is None
        and not signals.get("cjk_latin")
    ):
        return "无共现/嵌入/中英形态信号"
    return None


def _rule_fast_auto(
    entity_type: str, left: EntityLexicon, right: EntityLexicon, signals: Dict[str, Any]
) -> bool:
    """org 等：强共现 + CJK↔Latin 可跳过 LLM 自动并；product/drug 不做规则自动。"""
    if entity_type in ("product", "drug"):
        return False
    if not signals.get("cjk_latin"):
        return False
    if int(signals.get("cooccur") or 0) < _COOCCUR_AUTO_ORG:
        return False
    # 预处理变体
    if preprocess(left.canonical) == preprocess(right.canonical):
        return True
    return True


def _apply_auto_merge(
    session: Session,
    left: EntityLexicon,
    right: EntityLexicon,
    *,
    preferred_canonical: str,
    score: float,
    signals: Dict[str, Any],
    reason: str,
) -> EntityMergeCandidate:
    keep, drop = _pick_keep_drop(left, right, preferred_canonical)
    merge_entities(session, keep.id, drop.id)
    if keep.status == "pending":
        keep.status = "active"
    cand = _upsert_candidate(
        session,
        entity_type=keep.entity_type,
        left_id=left.id,
        right_id=right.id,
        score=score,
        signals={**signals, "keep_id": keep.id, "drop_id": drop.id},
        llm_reason=reason,
        preferred_keep_id=keep.id,
        status="auto",
    )
    logger.info(
        "实体自动合并 type=%s keep=%s(%s) drop=%s(%s) score=%.3f",
        keep.entity_type,
        keep.id,
        keep.canonical,
        drop.id,
        drop.canonical,
        score,
    )
    return cand


def resolve_entity_aliases(
    session: Session,
    *,
    limit: int = _DEFAULT_LIMIT,
    use_embedding: bool = True,
) -> Dict[str, Any]:
    """批处理入口：生成候选 → 判定 → 自动合并或入待审。"""
    by_type = _load_lexicon_map(session)
    decided = _existing_decided_pairs(session)
    co_bag = collect_cooccurrence_pairs(session, by_type)
    morph_bag = collect_morphology_pairs(by_type)
    emb_bag: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
    if use_embedding:
        emb_bag = collect_embedding_pairs(by_type)
    merged = _merge_signal_bags(co_bag, morph_bag, emb_bag)

    # 优先：有共现 > 有嵌入 > 仅形态；再按 cooccur/embed 排序
    def sort_key(item: Tuple[Tuple[str, int, int], Dict[str, Any]]):
        _k, sig = item
        return (
            int(sig.get("cooccur") or 0),
            float(sig.get("embed_sim") or 0.0),
            1 if sig.get("cjk_latin") else 0,
        )

    ranked = sorted(merged.items(), key=sort_key, reverse=True)
    stats = {
        "candidates_seen": 0,
        "skipped_decided": 0,
        "fast_reject": 0,
        "auto_merged": 0,
        "queued": 0,
        "dropped_low": 0,
        "llm_errors": 0,
        "limit": limit,
    }

    id_map = {
        r.id: r
        for rows in by_type.values()
        for r in rows
    }

    processed = 0
    for (et, left_id, right_id), signals in ranked:
        if processed >= limit:
            break
        pair = _ordered_ids(left_id, right_id)
        if pair in decided:
            stats["skipped_decided"] += 1
            continue
        left = id_map.get(left_id)
        right = id_map.get(right_id)
        if left is None or right is None:
            continue
        if left.status == "merged" or right.status == "merged":
            continue
        stats["candidates_seen"] += 1
        reject = _rule_fast_reject(left, right, signals)
        if reject:
            stats["fast_reject"] += 1
            continue

        processed += 1

        if _rule_fast_auto(et, left, right, signals):
            _apply_auto_merge(
                session,
                left,
                right,
                preferred_canonical="",
                score=0.9,
                signals=signals,
                reason=f"规则快通：共现{signals.get('cooccur')}且CJK↔Latin",
            )
            stats["auto_merged"] += 1
            decided.add(pair)
            continue

        try:
            verdict = _run_coro(
                _llm_judge(
                    entity_type=et, left=left, right=right, signals=signals
                )
            )
        except Exception as exc:
            logger.warning("别名裁判失败 %s/%s: %s", left_id, right_id, exc)
            stats["llm_errors"] += 1
            continue

        same = bool(verdict.get("same_entity"))
        conf = float(verdict.get("confidence") or 0.0)
        reason = str(verdict.get("reason") or "")
        pref = str(verdict.get("preferred_canonical") or "")
        auto_th = _AUTO_THRESH.get(et, 0.9)

        if same and conf >= auto_th:
            _apply_auto_merge(
                session,
                left,
                right,
                preferred_canonical=pref,
                score=conf,
                signals=signals,
                reason=reason or "LLM高置信自动合并",
            )
            stats["auto_merged"] += 1
            decided.add(pair)
        elif same and conf >= _REVIEW_FLOOR:
            keep, _drop = _pick_keep_drop(left, right, pref)
            _upsert_candidate(
                session,
                entity_type=et,
                left_id=left_id,
                right_id=right_id,
                score=conf,
                signals=signals,
                llm_reason=reason,
                preferred_keep_id=keep.id,
                status="pending",
            )
            stats["queued"] += 1
        else:
            stats["dropped_low"] += 1

    session.flush()
    logger.info("实体别名解析完成 stats=%s", stats)
    return stats


def list_merge_candidates(
    session: Session,
    *,
    status: Optional[str] = "pending",
    entity_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    stmt = select(EntityMergeCandidate).order_by(
        EntityMergeCandidate.score.desc(), EntityMergeCandidate.id.desc()
    )
    if status:
        stmt = stmt.where(EntityMergeCandidate.status == status)
    if entity_type:
        stmt = stmt.where(EntityMergeCandidate.entity_type == entity_type)
    rows = list(session.scalars(stmt).all())
    total = len(rows)
    page = rows[offset : offset + limit]
    items = []
    for row in page:
        left = session.get(EntityLexicon, row.left_id)
        right = session.get(EntityLexicon, row.right_id)
        items.append(
            {
                "id": row.id,
                "entity_type": row.entity_type,
                "left_id": row.left_id,
                "right_id": row.right_id,
                "left": {
                    "id": left.id if left else None,
                    "canonical": left.canonical if left else None,
                    "aliases": (left.aliases if left else None) or [],
                    "status": left.status if left else None,
                },
                "right": {
                    "id": right.id if right else None,
                    "canonical": right.canonical if right else None,
                    "aliases": (right.aliases if right else None) or [],
                    "status": right.status if right else None,
                },
                "score": row.score,
                "signals": row.signals or {},
                "llm_reason": row.llm_reason,
                "preferred_keep_id": row.preferred_keep_id,
                "status": row.status,
                "created_at": str(row.created_at) if row.created_at else None,
                "updated_at": str(row.updated_at) if row.updated_at else None,
            }
        )
    return {"total": total, "items": items}


def accept_merge_candidate(session: Session, candidate_id: int) -> Dict[str, Any]:
    row = session.get(EntityMergeCandidate, candidate_id)
    if row is None:
        raise ValueError("候选不存在")
    if row.status not in ("pending",):
        raise ValueError(f"状态不可接受: {row.status}")
    left = session.get(EntityLexicon, row.left_id)
    right = session.get(EntityLexicon, row.right_id)
    if left is None or right is None:
        raise ValueError("实体已不存在")
    if left.status == "merged" or right.status == "merged":
        row.status = "accepted"
        session.flush()
        raise ValueError("实体已合并，请刷新")
    pref = ""
    if row.preferred_keep_id:
        keep_row = session.get(EntityLexicon, row.preferred_keep_id)
        if keep_row:
            pref = keep_row.canonical
    keep, drop = _pick_keep_drop(left, right, pref)
    merge_entities(session, keep.id, drop.id)
    if keep.status == "pending":
        keep.status = "active"
    row.status = "accepted"
    row.preferred_keep_id = keep.id
    signals = dict(row.signals or {})
    signals["keep_id"] = keep.id
    signals["drop_id"] = drop.id
    row.signals = signals
    session.flush()
    return {
        "candidate_id": row.id,
        "keep_id": keep.id,
        "drop_id": drop.id,
        "canonical": keep.canonical,
    }


def reject_merge_candidate(session: Session, candidate_id: int) -> Dict[str, Any]:
    row = session.get(EntityMergeCandidate, candidate_id)
    if row is None:
        raise ValueError("候选不存在")
    row.status = "rejected"
    session.flush()
    return {"candidate_id": row.id, "status": "rejected"}


def run_alias_resolve(*, limit: int = _DEFAULT_LIMIT, use_embedding: bool = True) -> Dict[str, Any]:
    from backend.src.db.session import session_scope

    with session_scope() as session:
        return resolve_entity_aliases(
            session, limit=limit, use_embedding=use_embedding
        )
