# -*- coding: utf-8 -*-
"""
面向医药竞争情报的流式新闻在线聚类核心引擎
包含：融合相似度（语义+实体加权+时间衰减）、Otsu 自适应阈值、多代表 medoid、事件生命周期
决策原则：医药实体（药物+事件类型）一致是同一事件的最强信号；无实体匹配时用自适应语义阈值。
"""
import numpy as np
from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


# 平台方 / 媒体 / 通讯社：不是事件的“核心企业”，比较时排除
PLATFORM_ORGS = (
    "newsweek", "statista", "prnewswire", "globenewswire", "businesswire",
    "nasdaq", "globe newswire", "hellonation",
)


def core_orgs(orgs: set) -> set:
    """剔除平台方后的核心企业。"""
    return {x for x in orgs if not any(p in x for p in PLATFORM_ORGS)}


def core_drugs(drugs: set, limit: int = 3) -> set:
    """药物数<=3视为单一药物事件；罗列过多（市场报告）视为无核心药物。"""
    return drugs if len(drugs) <= limit else set()


def entity_match(a: set, b: set) -> float:
    """实体匹配度：1.0 精确交集 / 0.8 包含 / 0.7 前缀相似 / 0.0 无。
    用于容忍跨语言、跨写法的同一实体（如 navepegritide / navepegritid）。"""
    if not a or not b:
        return 0.0
    if a & b:
        return 1.0
    for x in a:
        for y in b:
            if x in y or y in x:
                return 0.8
            n = min(len(x), len(y))
            if n >= 7 and x[:n - 2] == y[:n - 2]:
                return 0.7
    return 0.0


@dataclass
class Article:
    id: str
    text: str                              # 用于聚类的文本（摘要）
    timestamp: float                       # Unix 时间戳（秒）
    embedding: np.ndarray
    drug_entities: Set[str] = field(default_factory=set)
    org_entities: Set[str] = field(default_factory=set)
    event_type: str = ""                   # 事件类型：clinical / approval / m&a / safety ...


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
        drugs, orgs, types = set(), set(), set()
        for m in self.members:
            drugs |= m.drug_entities
            orgs |= m.org_entities
            if m.event_type:
                types.add(m.event_type)
        return drugs, orgs, types

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
    """
    Otsu 自适应阈值：把历史“最大相似度”看作双峰分布（归入高 / 新建低），
    自动找类间方差最大的谷底作为低阈值 theta_low；
    高阈值 theta_high 取高分组的下沿。
    """

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
            self.theta_high = float(np.clip(high.mean() - 0.5 * high.std(),
                                           self.theta_low + 0.05, 0.95))
        else:
            self.theta_high = self.theta_low + 0.15


class StreamingClusterer:
    def __init__(
        self,
        alpha: float = 0.7,
        beta: float = 0.3,
        tau_seconds: float = 14 * 24 * 3600,
        n_medoids: int = 3,
        archive_seconds: float = 30 * 24 * 3600,
    ):
        self.alpha = alpha
        self.beta = beta
        self.tau = tau_seconds
        self.archive = archive_seconds
        self.n_medoids = n_medoids
        self.clusters: List[EventCluster] = []
        self.threshold = AdaptiveThreshold()
        self._cid = 0

    @staticmethod
    def _jaccard(a: set, b: set) -> float:
        if not a and not b:
            return 0.0
        u = len(a | b)
        return len(a & b) / u if u else 0.0

    def _signals(self, art: Article, c: EventCluster) -> Tuple[float, float, float, float, float]:
        """返回 (融合相似度, 药物Jaccard, 实体综合重叠, 事件标识匹配度, 纯语义相似度)"""
        drugs, orgs, types = c.entity_sets()
        dj = self._jaccard(art.drug_entities, drugs)
        oj = self._jaccard(art.org_entities, orgs)
        tj = 1.0 if (art.event_type and art.event_type in types) else 0.0

        # 核心实体（剔除平台方、识别“罗列药物”的市场报告）
        cd_art = core_drugs(art.drug_entities)
        cd_clu = core_drugs(drugs)
        co_art = core_orgs(art.org_entities)
        co_clu = core_orgs(orgs)

        # 统一“事件标识”：药物优先，无药物则用核心企业
        key_art = cd_art if cd_art else co_art
        key_clu = cd_clu if cd_clu else co_clu
        match = entity_match(key_art, key_clu)
        # 双方标识都明确且判定为不匹配 → 否决合并
        if key_art and key_clu and match == 0.0:
            return 0.0, 0.0, 0.0, 0.0, 0.0

        ent = 0.6 * dj + 0.25 * oj + 0.15 * tj
        best = 0.0
        best_cos = 0.0
        for med in c.medoids:
            cs = cosine(art.embedding, med.embedding)
            best_cos = max(best_cos, cs)
            decay = np.exp(-abs(art.timestamp - med.timestamp) / self.tau)
            best = max(best, (self.alpha * cs + self.beta * ent) * decay)
        return best, dj, ent, match, best_cos

    def ingest(self, art: Article):
        active = [c for c in self.clusters if c.status != "archived"]
        if not active:
            self._new_cluster(art)
            return

        results = [(c, *self._signals(art, c)) for c in active]
        cbest, fbest, djbest, ebest, mbest, cosbest = max(
            results, key=lambda x: x[1])
        self.threshold.add(fbest)
        self.threshold.update()

        # 双方是否都没有实体标识
        cd_b, co_b, _ = cbest.entity_sets()
        clu_has_key = bool(core_drugs(cd_b)) or bool(core_orgs(co_b))
        art_has_key = bool(core_drugs(art.drug_entities)) or \
            bool(core_orgs(art.org_entities))

        lo, hi = self.threshold.theta_low, self.threshold.theta_high
        # 规则1：核心事件标识一致（药物/企业，含跨写法模糊匹配）→ 同一事件
        if mbest >= 0.7:
            self._add_to(cbest, art)
            return
        # 规则2：只要有一方无实体标识（无法用实体互相确认），
        # 必须纯语义足够高才合并，否则新建。
        # 阈值0.80：实测同事件>=0.84，模板化不同事件<=0.74。
        if not art_has_key or not clu_has_key:
            if cosbest >= 0.80:
                self._add_to(cbest, art)
            else:
                self._new_cluster(art)
            return
        # 规则3：走自适应融合阈值
        if fbest >= hi:
            self._add_to(cbest, art)
        elif fbest < lo:
            self._new_cluster(art)
        else:
            # 灰区：实体弱一致，或语义落在灰区上半段 → 归入
            mid = lo + 0.5 * (hi - lo)
            if ebest >= 0.3 or fbest >= mid:
                self._add_to(cbest, art)
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
            if c.status != "archived" and now - c.updated_at > self.archive:
                c.status = "archived"
#（注：内容由AI生成）
