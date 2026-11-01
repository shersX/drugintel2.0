# -*- coding: utf-8 -*-
"""
面向医药竞争情报的流式新闻在线聚类核心引擎

相对经典 Single-pass 的领域增强：
1. 产品级实体优先（wegovy / cagrisema）；成分重叠但产品不同 → 禁止仅凭成分合并
2. 企业单独不算强事件键（避免“只有 Pfizer”的泛新闻并爆）
3. 弱实体 / 无实体：纯余弦三档（对齐生产口述规则）
   - cos ≥ 0.90 → 归入最佳簇
   - 0.80 ≤ cos < 0.90 → 与该簇全部成员比对，任一 ≥ 0.90 才归入，否则新建
   - cos < 0.80 → 新建
4. 按事件类型长生命周期；产品强一致时弱化时间衰减
5. 多 medoid 用于挑候选簇与融合分
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple, Dict


DAY = 24 * 3600

LIFECYCLE: Dict[str, Tuple[float, float]] = {
    "clinical": (365 * DAY, 730 * DAY),
    "approval": (365 * DAY, 730 * DAY),
    "safety": (60 * DAY, 180 * DAY),
    "m&a": (180 * DAY, 365 * DAY),
    "other": (180 * DAY, 365 * DAY),
}
DEFAULT_TAU, DEFAULT_ARCHIVE = 180 * DAY, 365 * DAY

# 弱实体路径：纯余弦阈值（与 drugintel 口述规则对齐；本目录实验用）
COS_HIGH = 0.90
COS_MID = 0.80


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


PLATFORM_ORGS = (
    "newsweek", "statista", "prnewswire", "globenewswire", "businesswire",
    "nasdaq", "globe newswire", "hellonation", "fda",
)


def core_orgs(orgs: set) -> set:
    return {x for x in orgs if not any(p in x for p in PLATFORM_ORGS)}


def core_drugs(drugs: set, limit: int = 3) -> set:
    return drugs if len(drugs) <= limit else set()


def _common_prefix_len(x: str, y: str) -> int:
    n = min(len(x), len(y))
    i = 0
    while i < n and x[i] == y[i]:
        i += 1
    return i


def entity_match(a: set, b: set) -> float:
    """1.0 精确 / 0.8 包含 / 0.7 长前缀 / 0.0 无。"""
    if not a or not b:
        return 0.0
    if a & b:
        return 1.0
    for x in a:
        for y in b:
            if x in y or y in x:
                return 0.8
            shorter = min(len(x), len(y))
            if shorter < 7:
                continue
            pref = _common_prefix_len(x, y)
            if pref >= 7 and pref >= 0.8 * shorter:
                return 0.7
    return 0.0


def lifecycle_for(event_type: str) -> Tuple[float, float]:
    return LIFECYCLE.get((event_type or "other").lower(), (DEFAULT_TAU, DEFAULT_ARCHIVE))


def has_strong_entity(products: set, drugs: set) -> bool:
    """强事件键：产品或成分；仅公司不算强键。"""
    return bool(products) or bool(core_drugs(drugs))


@dataclass
class Article:
    id: str
    text: str
    timestamp: float
    embedding: np.ndarray
    drug_entities: Set[str] = field(default_factory=set)
    org_entities: Set[str] = field(default_factory=set)
    event_type: str = ""
    product_entities: Set[str] = field(default_factory=set)


@dataclass
class EventCluster:
    id: int
    members: List[Article] = field(default_factory=list)
    medoids: List[Article] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    n_medoids: int = 3
    status: str = "active"

    def entity_sets(self):
        drugs, orgs, types, products = set(), set(), set(), set()
        for m in self.members:
            drugs |= m.drug_entities
            orgs |= m.org_entities
            products |= m.product_entities
            if m.event_type:
                types.add(m.event_type)
        return drugs, orgs, types, products

    def update_medoids(self):
        if len(self.members) <= self.n_medoids:
            self.medoids = list(self.members)
            return
        embs = np.array([m.embedding for m in self.members], dtype=np.float64)
        norm = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9)
        sim = norm @ norm.T
        idx = np.argsort(-sim.mean(axis=1))[: self.n_medoids]
        self.medoids = [self.members[i] for i in idx]


class AdaptiveThreshold:
    """融合分自适应双阈（主要用于强实体路径的辅助决策）。"""

    def __init__(self, window: int = 300):
        self.scores: List[float] = []
        self.window = window
        self.theta_low = 0.35
        self.theta_high = 0.55

    def add(self, s: float):
        self.scores.append(s)
        if len(self.scores) > self.window:
            self.scores = self.scores[-self.window:]

    @staticmethod
    def _otsu(scores: np.ndarray) -> Optional[float]:
        if len(scores) < 4:
            return None
        bins = 20
        hist, edges = np.histogram(scores, bins=bins, range=(0.0, 1.0))
        total = hist.sum()
        centers = (edges[:-1] + edges[1:]) / 2
        sum_total = np.dot(hist, centers)
        wb, sb, best_var, thr = 0, 0.0, 0.0, None
        for i in range(bins):
            wb += hist[i]
            if wb == 0:
                continue
            wf = total - wb
            if wf == 0:
                break
            sb += hist[i] * centers[i]
            mb = sb / wb
            mf = (sum_total - sb) / wf
            var = wb * wf * (mb - mf) ** 2
            if var > best_var:
                best_var = var
                thr = centers[i]
        return thr

    def update(self):
        if len(self.scores) < 4:
            return
        arr = np.array(self.scores)
        t = self._otsu(arr)
        if t is None:
            return
        self.theta_low = float(np.clip(t, 0.15, 0.80))
        high = arr[arr > t]
        if len(high) >= 2:
            self.theta_high = float(np.clip(
                high.mean() - 0.5 * high.std(),
                self.theta_low + 0.05, 0.95))
        else:
            self.theta_high = self.theta_low + 0.15


class StreamingClusterer:
    def __init__(
        self,
        alpha: float = 0.7,
        beta: float = 0.3,
        tau_seconds: float = DEFAULT_TAU,
        n_medoids: int = 3,
        archive_seconds: float = DEFAULT_ARCHIVE,
        use_typed_lifecycle: bool = True,
        cos_high: float = COS_HIGH,
        cos_mid: float = COS_MID,
    ):
        self.alpha = alpha
        self.beta = beta
        self.tau = tau_seconds
        self.archive = archive_seconds
        self.use_typed_lifecycle = use_typed_lifecycle
        self.n_medoids = n_medoids
        self.cos_high = cos_high
        self.cos_mid = cos_mid
        self.clusters: List[EventCluster] = []
        self.threshold = AdaptiveThreshold()
        self._cid = 0

    @staticmethod
    def _jaccard(a: set, b: set) -> float:
        if not a and not b:
            return 0.0
        u = len(a | b)
        return len(a & b) / u if u else 0.0

    def _tau_for(self, art: Article, c: EventCluster) -> float:
        if not self.use_typed_lifecycle:
            return self.tau
        taus = [lifecycle_for(art.event_type)[0]]
        for m in c.members:
            taus.append(lifecycle_for(m.event_type)[0])
        return max(taus)

    def _max_cos_to_members(self, art: Article, c: EventCluster) -> float:
        """与簇内全部成员的最大余弦（灰区复核用）。"""
        best = 0.0
        for m in c.members:
            best = max(best, cosine(art.embedding, m.embedding))
        return best

    def _max_cos_to_medoids(self, art: Article, c: EventCluster) -> float:
        best = 0.0
        for med in c.medoids or c.members[:1]:
            best = max(best, cosine(art.embedding, med.embedding))
        return best

    def _signals(self, art: Article, c: EventCluster):
        """
        返回:
          fused, dj, ent, product_match, ingredient_match, cos_medoid, product_conflict
        """
        drugs, orgs, types, products = c.entity_sets()
        dj = self._jaccard(art.drug_entities, drugs)
        oj = self._jaccard(art.org_entities, orgs)
        tj = 1.0 if (art.event_type and art.event_type in types) else 0.0

        prod_art = {x.lower() for x in art.product_entities if x}
        prod_clu = {x.lower() for x in products if x}
        pmatch = entity_match(prod_art, prod_clu)
        product_conflict = bool(prod_art and prod_clu and pmatch == 0.0)

        cd_art = core_drugs(art.drug_entities)
        cd_clu = core_drugs(drugs)
        imatch = entity_match(cd_art, cd_clu)

        if product_conflict:
            return 0.0, 0.0, 0.0, 0.0, imatch, 0.0, True

        co_art = core_orgs(art.org_entities)
        co_clu = core_orgs(orgs)
        if prod_art or prod_clu:
            if prod_art and prod_clu:
                key_match = pmatch
            else:
                key_match = imatch * 0.5
        else:
            # 无产品时：成分可作键；公司不单独否决/强并
            if cd_art and cd_clu:
                key_match = imatch
                if key_match == 0.0:
                    # 成分明确不同 → 不在强路径用融合分硬拉，但弱路径仍可比余弦
                    key_match = 0.0
            else:
                key_match = 0.0  # 仅公司 / 全空 → 弱实体

        ent = 0.5 * max(pmatch, imatch) + 0.2 * dj + 0.15 * oj + 0.15 * tj
        tau = self._tau_for(art, c)
        strong_product = pmatch >= 0.7

        best = 0.0
        best_cos = 0.0
        for med in c.medoids:
            cs = cosine(art.embedding, med.embedding)
            best_cos = max(best_cos, cs)
            decay = 1.0 if strong_product else float(
                np.exp(-abs(art.timestamp - med.timestamp) / tau))
            best = max(best, (self.alpha * cs + self.beta * ent) * decay)

        if prod_art and prod_clu:
            match_out = pmatch
        else:
            match_out = max(pmatch, imatch, key_match)
        return best, dj, ent, match_out, imatch, best_cos, False

    def _decide_by_cosine_tiers(self, art: Article, c: EventCluster, cos_ref: float) -> bool:
        """
        弱实体三档：
          ≥ high → 归入
          [mid, high) → 与全部成员比，任一 ≥ high 才归入
          < mid → 新建
        返回是否归入 c。
        """
        if cos_ref >= self.cos_high:
            return True
        if cos_ref < self.cos_mid:
            return False
        # 灰区：全员复核
        return self._max_cos_to_members(art, c) >= self.cos_high

    def ingest(self, art: Article):
        active = [c for c in self.clusters if c.status != "archived"]
        if not active:
            self._new_cluster(art)
            return

        results = [(c, *self._signals(art, c)) for c in active]
        viable = [r for r in results if not r[7]]
        pool = viable if viable else results

        # 候选簇：优先融合分；弱实体场景同时看 medoid 余弦
        cbest, fbest, djbest, ebest, pbest, ibest, cosbest, conflict = max(
            pool, key=lambda x: (x[1], x[6]))

        self.threshold.add(fbest)
        self.threshold.update()

        if conflict and not viable:
            self._new_cluster(art)
            return

        drugs_b, orgs_b, _, products_b = cbest.entity_sets()
        art_strong = has_strong_entity(art.product_entities, art.drug_entities)
        clu_strong = has_strong_entity(products_b, drugs_b)

        # ---------- 强实体路径：产品 / 成分 ----------
        if art_strong and clu_strong:
            # 双方产品都有且不一致 → 新建
            if art.product_entities and products_b and entity_match(
                    {x.lower() for x in art.product_entities},
                    {x.lower() for x in products_b}) == 0.0:
                self._new_cluster(art)
                return
            # 产品或成分强一致 → 归入
            if pbest >= 0.7:
                self._add_to(cbest, art)
                return
            # 强实体但对不上：回落到余弦三档（对最佳余弦簇）
            # 重新按 medoid 余弦选簇，避开产品冲突簇
            cos_pool = []
            for row in viable:
                c = row[0]
                cos_pool.append((c, self._max_cos_to_medoids(art, c)))
            if not cos_pool:
                self._new_cluster(art)
                return
            c2, cos_ref = max(cos_pool, key=lambda x: x[1])
            if self._decide_by_cosine_tiers(art, c2, cos_ref):
                self._add_to(c2, art)
            else:
                self._new_cluster(art)
            return

        # ---------- 弱实体路径：仅公司 / 无实体 / 一侧无强键 ----------
        # 按与各簇 medoid 最大余弦选候选（不靠公司名硬并）
        cos_pool = []
        for row in (viable or results):
            c = row[0]
            # 若新文有产品、簇有不同产品，仍跳过
            _, _, _, prods = c.entity_sets()
            if art.product_entities and prods and entity_match(
                    {x.lower() for x in art.product_entities},
                    {x.lower() for x in prods}) == 0.0:
                continue
            cos_pool.append((c, self._max_cos_to_medoids(art, c)))
        if not cos_pool:
            self._new_cluster(art)
            return
        c2, cos_ref = max(cos_pool, key=lambda x: x[1])
        if self._decide_by_cosine_tiers(art, c2, cos_ref):
            self._add_to(c2, art)
        else:
            self._new_cluster(art)

    def _add_to(self, c: EventCluster, art: Article):
        c.members.append(art)
        c.updated_at = art.timestamp
        c.update_medoids()

    def _new_cluster(self, art: Article):
        self._cid += 1
        c = EventCluster(id=self._cid, created_at=art.timestamp,
                         updated_at=art.timestamp, n_medoids=self.n_medoids)
        c.members = [art]
        c.medoids = [art]
        self.clusters.append(c)

    def maintain(self, now: float):
        for c in self.clusters:
            if c.status == "archived":
                continue
            archive = self.archive
            if self.use_typed_lifecycle:
                archive = max(lifecycle_for(m.event_type)[1] for m in c.members) \
                    if c.members else self.archive
            if now - c.updated_at > archive:
                c.status = "archived"
