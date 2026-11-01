# -*- coding: utf-8 -*-
"""
事件趋势 / 风险预测模块（接在流式聚类之后）
- 任务1：预测事件簇下一时间窗的报道量（回归，热度预测）
- 任务2：预测事件是否会“爆发”（分类，竞争/风险预警）
标签全部由新闻时间序列自动构造，无需历史结局库。
"""
import numpy as np
from typing import List, Tuple

DAY = 24 * 3600


class EventTrendPredictor:
    def __init__(self, bin_seconds: float = DAY,
                 burst_ratio: float = 1.5, burst_min: float = 2.0):
        self.bin = bin_seconds           # 时间桶宽（默认 1 天）
        self.burst_ratio = burst_ratio   # 爆发判定：未来量 >= 当前量 * 比例
        self.burst_min = burst_min       # 且未来量至少为该值
        self.reg = None
        self.clf = None
        self.type_vocab = {}

    # ---- 把一个事件簇按时间桶统计成报道量序列 ----
    def _series(self, cluster):
        t0 = cluster.created_at
        n = max(1, int((cluster.updated_at - t0) / self.bin) + 1)
        counts = np.zeros(n + 2)
        type_at = {}
        for m in cluster.members:
            b = int((m.timestamp - t0) / self.bin)
            if 0 <= b < len(counts):
                counts[b] += 1
                if m.event_type:
                    type_at.setdefault(b, set()).add(m.event_type)
        return counts, type_at

    def _type_vec(self, etype: str) -> np.ndarray:
        v = np.zeros(len(self.type_vocab))
        if etype in self.type_vocab:
            v[self.type_vocab[etype]] = 1.0
        return v

    # ---- 特征：在时刻 t 截取的历史窗口 ----
    def _feat(self, counts, t, total, type_at):
        def g(i):
            return counts[i] if 0 <= i < len(counts) else 0.0
        c1, c2, c3 = g(t), g(t - 1), g(t - 2)
        rate = (c1 - c2) / (c2 + 1.0)          # 增长率
        accel = (c1 - c2) - (c2 - c3)          # 加速度
        etype = next(iter(type_at.get(t, set())), "")
        tv = self._type_vec(etype)
        return np.concatenate([[c1, c2, c3, rate, accel, total, t], tv])

    # ---- 自动构造训练集 ----
    def build_dataset(self, clusters) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        types = sorted({m.event_type for c in clusters for m in c.members
                        if m.event_type})
        self.type_vocab = {t: i for i, t in enumerate(types)}

        X, y_reg, y_clf = [], [], []
        for c in clusters:
            counts, type_at = self._series(c)
            total = len(c.members)
            for t in range(1, len(counts) - 1):
                X.append(self._feat(counts, t, total, type_at))
                fut = counts[t + 1]
                cur = counts[t]
                y_reg.append(fut)
                y_clf.append(1 if fut >= self.burst_min
                             and fut >= cur * self.burst_ratio else 0)
        if not X:
            raise ValueError("样本不足：需要更长的事件时间序列")
        return np.array(X), np.array(y_reg), np.array(y_clf)

    # ---- 训练 ----
    def fit(self, clusters):
        from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
        X, yr, yc = self.build_dataset(clusters)
        self.reg = GradientBoostingRegressor(max_depth=2, n_estimators=120,
                                             random_state=0)
        self.reg.fit(X, yr)
        self.clf = GradientBoostingClassifier(max_depth=2, n_estimators=120,
                                              random_state=0)
        self.clf.fit(X, yc)
        return self

    # ---- 对一个事件簇的当前状态做预测 ----
    def predict_cluster(self, cluster) -> dict:
        counts, type_at = self._series(cluster)
        # 定位到“最后一个有数据的桶”，预测它的下一桶
        nonzero = np.where(counts > 0)[0]
        t = int(nonzero[-1]) if len(nonzero) else 0
        feat = self._feat(counts, t, len(cluster.members), type_at).reshape(1, -1)
        next_count = float(self.reg.predict(feat)[0])
        proba = self.clf.predict_proba(feat)[0]
        classes = list(self.clf.classes_)
        p_burst = float(proba[classes.index(1)]) if 1 in classes else 0.0
        return {"next_count": max(0.0, next_count), "burst_prob": p_burst}
