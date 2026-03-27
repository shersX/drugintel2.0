# DrugIntel.ai 产品需求文档 (PRD)

## 文档信息

| 项目 | 内容 |
|------|------|
| 产品名称 | DrugIntel.ai - 医药情报AI平台 |
| 文档版本 | V1.0 |
| 创建日期 | 2026-03-26 |
| 文档状态 | 草稿 |
| 目标读者 | 开发团队 |
| 项目性质 | 毕业设计 |

### 版本历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| V1.0 | 2026-03-26 | 开发团队 | 初始版本 |

### 术语表

| 术语 | 说明 |
|------|------|
| RAG | Retrieval-Augmented Generation，检索增强生成 |
| Embedding | 文本向量化表示 |
| pgvector | PostgreSQL的向量扩展插件 |
| NER | Named Entity Recognition，命名实体识别 |
| LLM | Large Language Model，大语言模型 |
| Watchlist | 监控列表，用户订阅的实体清单 |

---

## 2. 产品概述

### 2.1 项目背景

医药行业信息量大、更新频繁，研发人员、分析师和投资者需要持续跟踪新闻、临床试验、监管公告等多源信息。传统的人工检索方式效率低下，难以快速获取关键情报。

DrugIntel.ai 旨在通过自动化采集、智能处理和语义分析，为用户提供一站式的医药情报服务。

### 2.2 产品目标

| 目标 | 描述 |
|------|------|
| **自动化采集** | 自动抓取多源医药新闻，减少人工检索成本 |
| **智能处理** | 通过 NLP 技术实现去重、摘要、实体识别 |
| **语义检索** | 支持向量检索，实现语义级别的新闻搜索 |
| **智能问答** | 基于 RAG 技术，提供自然语言问答服务 |
| **主动告警** | 监控关键实体，实时推送相关动态 |

### 2.3 目标用户

| 用户角色 | 需求场景 |
|----------|----------|
| **医药研发人员** | 跟踪竞品药物进展、临床试验结果 |
| **投资分析师** | 监控药企动态、并购事件、监管审批 |
| **医药企业** | 竞品情报收集、行业趋势分析 |

### 2.4 功能范围

#### 已有功能

| 模块 | 功能点 |
|------|--------|
| 数据采集 | 多源爬虫（Bioon、GlobeNewswire等）、新闻抓取 |
| 数据处理 | 文本清洗、LLM摘要、向量化、去重 |
| 数据存储 | PostgreSQL + pgvector 向量存储 |
| 搜索检索 | 全文搜索、向量检索、混合搜索 |
| API服务 | RESTful API、健康检查 |
| 前端应用 | 新闻列表、详情页、研发进度查询 |

#### 新增功能

| 模块 | 功能点 | 优先级 |
|------|--------|--------|
| RAG智慧问答 | 多轮对话、混合检索、LLM生成 | P0 |
| 告警通知 | 邮件推送、Watchlist监控 | P1 |

| 核心数据展示 | 研发进度统计、新闻趋势 | P2 |
| 轻量级监控 | 爬虫状态、处理状态、系统状态 | P2 |

### 2.5 技术栈

| 层次 | 技术选型 |
|------|----------|
| 后端框架 | FastAPI |
| 数据库 | PostgreSQL + pgvector |
| 向量模型 | BGE-M3 (1024维) |
| LLM服务 | SiliconFlow API |
| 前端框架 | Vue 3 + Vite |
| 任务调度 | Celery + Redis |
| 部署方式 | Docker Compose |

---

## 3. 系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           前端应用层 (Vue 3)                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ 新闻列表  │ │ 新闻详情  │ │ RAG问答  │ │ 告警管理  │ │ 系统监控  │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           API 服务层 (FastAPI)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ /news    │ │ /search  │ │ /chat    │ │ /alert   │ │ /monitor │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           业务逻辑层                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ RAG引擎   │ │ 告警引擎  │ │ 导出服务  │ │ 监控服务  │ │ 事件抽取  │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           数据处理层                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│  │ 文本清洗  │ │ 向量生成  │ │ 摘要生成  │ │ 实体识别  │                   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           数据采集层                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│  │ Bioon    │ │GlobeNews │ │PRNewswire│ │Business  │                   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           数据存储层                                     │
│  ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐  │
│  │ PostgreSQL         │ │ pgvector           │ │ Redis              │  │
│  │ (结构化数据)        │ │ (向量索引)          │ │ (缓存/队列)         │  │
│  └────────────────────┘ └────────────────────┘ └────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流图

```
┌─────────────┐
│  外部数据源  │
└──────┬──────┘
       │ 爬虫抓取
       ▼
┌─────────────┐     ┌─────────────┐
│  原始新闻    │────▶│  关键词过滤  │
└─────────────┘     └──────┬──────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  标题去重    │     │  LLM摘要    │     │  向量生成    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
                    ┌─────────────┐
                    │  相似度过滤  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  数据入库    │
                    └──────┬──────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  API查询    │     │  RAG问答    │     │  告警推送    │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 3.3 模块划分

| 模块 | 职责 | 依赖 |
|------|------|------|
| 数据采集模块 | 爬虫调度、新闻抓取、数据解析 | 无 |
| 数据处理模块 | 清洗、摘要、向量化、去重 | 数据采集 |
| 数据存储模块 | 数据库操作、向量索引 | 数据处理 |
| RAG问答模块 | 意图识别、检索、生成 | 数据存储 |
| 搜索检索模块 | 全文搜索、向量检索 | 数据存储 |
| 告警通知模块 | 规则匹配、邮件推送 | 数据存储 |
| 核心数据展示 | 统计指标计算 | 数据存储 |
| 轻量级监控 | 状态采集、展示 | 数据采集、数据处理 |
| API服务模块 | 接口暴露、请求处理 | 所有业务模块 |
| 前端应用模块 | 用户界面、交互 | API服务 |

---

## 4. 功能需求

### 4.1 数据采集模块

#### 4.1.1 功能描述

负责从多个数据源自动采集医药相关新闻，支持定时调度和增量抓取。

#### 4.1.2 数据源配置

| 数据源 | 类型 | URL | 更新频率 |
|--------|------|-----|----------|
| Bioon | 医药新闻 | https://www.bioon.com | 每日 |
| GlobeNewswire | 企业新闻稿 | https://www.globenewswire.com | 实时 |
| PRNewswire | 企业新闻稿 | https://www.prnewswire.com | 实时 |
| Businesswire | 企业新闻稿 | https://www.businesswire.com | 实时 |

#### 4.1.3 爬虫注册表设计

```python
CRAWLER_REGISTRY = {
    "bioon": {
        "enabled": True,
        "class": "BioonCrawler",
        "max_pages": 5,
        "concurrent": 3,
        "schedule": "0 8 * * *",  # 每日8点
    },
    "globenewswire": {
        "enabled": True,
        "class": "GlobeNewswireCrawler",
        "max_pages": 10,
        "concurrent": 5,
        "schedule": "0 */4 * * *",  # 每4小时
    },
    "prnewswire": {
        "enabled": True,
        "class": "PRNewswireCrawler",
        "max_pages": 10,
        "concurrent": 5,
        "schedule": "0 */4 * * *",
    },
    "businesswire": {
        "enabled": False,  # 可配置开关
        "class": "BusinessWireCrawler",
        "max_pages": 10,
        "concurrent": 5,
        "schedule": "0 */4 * * *",
    },
}
```

#### 4.1.4 数据结构

**原始新闻数据结构：**

```python
@dataclass
class RawNews:
    title: str              # 新闻标题
    content: str            # 新闻正文
    publish_time: datetime  # 发布时间
    source: str             # 来源名称
    detail_url: str         # 原文链接
    crawler: str            # 爬虫标识
    language: str = "zh"    # 语言标识
    extra: dict = None      # 扩展字段
```

#### 4.1.5 接口定义

```python
class BaseCrawler(ABC):
    @abstractmethod
    async def fetch_list(self, page: int) -> List[str]:
        """获取新闻列表页的URL列表"""
        pass
    
    @abstractmethod
    async def fetch_detail(self, url: str) -> RawNews:
        """获取新闻详情"""
        pass
    
    async def crawl(self, max_pages: int = 5) -> List[RawNews]:
        """执行爬取任务"""
        results = []
        for page in range(1, max_pages + 1):
            urls = await self.fetch_list(page)
            for url in urls:
                try:
                    news = await self.fetch_detail(url)
                    results.append(news)
                except Exception as e:
                    logger.error(f"爬取失败: {url}, 错误: {e}")
        return results
```

#### 4.1.6 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| 网络超时 | 重试3次，间隔递增（1s, 2s, 4s） |
| 页面解析失败 | 记录日志，跳过该条目 |
| 反爬限制 | 降低并发数，增加随机延迟 |
| 数据格式异常 | 记录原始数据，人工排查 |

---

### 4.2 数据处理模块

#### 4.2.1 功能描述

对采集的原始新闻进行清洗、相关性判断、摘要、向量化处理，入库后作为 raw_data，供后续事件聚类使用。

#### 4.2.2 处理流程

```
原始新闻 → 关键词过滤 → LLM相关性判断 → 标题去重 → LLM摘要 → 向量生成 → 入库(raw_data)
```

#### 4.2.3 关键词过滤

**关键词配置：**

```python
KEYWORDS = [
    # 药物相关
    "司美格鲁肽", "度拉糖肽", "替尔泊肽", "GLP-1", "胰岛素",
    # 公司相关
    "诺和诺德", "礼来", "辉瑞", "罗氏", "阿斯利康",
    # 事件相关
    "临床试验", "FDA批准", "NMPA", "并购", "上市",
    # 疾病相关
    "糖尿病", "肥胖症", "癌症", "心血管",
]

def filter_by_keywords(news: RawNews) -> Tuple[bool, List[str]]:
    """检查新闻是否匹配关键词"""
    text = f"{news.title} {news.content}"
    matched = [kw for kw in KEYWORDS if kw in text]
    return len(matched) > 0, matched
```

#### 4.2.4 LLM相关性判断

**判断新闻是否属于医药行业：**

```python
RELEVANCE_PROMPT = """请判断以下新闻是否与医药行业相关。
医药行业相关包括：药物研发、临床试验、监管审批、药企动态、疾病治疗等。

新闻标题：{title}
新闻内容：{content}

请只回答"是"或"否"："""

def check_relevance(title: str, content: str) -> bool:
    """判断新闻是否与医药行业相关"""
    prompt = RELEVANCE_PROMPT.format(title=title, content=content[:2000])
    response = llm_client.generate(prompt)
    return response.strip() == "是"
```

#### 4.2.5 标题去重

```python
def deduplicate_by_title(news_list: List[RawNews], db_session) -> List[RawNews]:
    """基于标题去重，过滤已存在的新闻"""
    existing_titles = set(
        db_session.query(News.title).filter(
            News.title.in_([n.title for n in news_list])
        ).all()
    )
    return [n for n in news_list if n.title not in existing_titles]
```

#### 4.2.6 LLM摘要生成

**摘要Prompt模板：**

```python
SUMMARY_PROMPT = """你是一个医药新闻摘要专家。请为以下新闻生成一段简洁的摘要（150-200字），包含：
1. 核心事件
2. 涉及的药物/公司
3. 关键数据或结论

新闻标题：{title}
新闻内容：{content}

请直接输出摘要内容，不要添加任何前缀："""

def generate_summary(title: str, content: str) -> str:
    prompt = SUMMARY_PROMPT.format(title=title, content=content[:3000])
    response = llm_client.generate(prompt)
    return response.strip()
```

#### 4.2.7 向量生成

```python
class EmbeddingManager:
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model = SentenceTransformer(model_name)
        self.dimension = 1024
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """生成文本向量"""
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings
    
    def encode_single(self, text: str) -> List[float]:
        """生成单个文本的向量"""
        embedding = self.model.encode([text], normalize_embeddings=True)
        return embedding[0].tolist()
```

#### 4.2.8 入库为 raw_data

处理完成的新闻作为 raw_data 入库，等待事件聚类处理：

```python
def save_raw_news(news: ProcessedNews, db_session):
    """保存处理后的新闻为raw_data"""
    raw_news = News(
        title=news.title,
        content=news.content,
        abstract=news.abstract,
        publish_time=news.publish_time,
        source=news.source,
        detail_url=news.detail_url,
        crawler=news.crawler,
        matched_keywords=news.matched_keywords,
        embedding=news.embedding,
        is_representative=False,  # 默认不是代表新闻
        event_id=None,  # 尚未聚类
    )
    db_session.add(raw_news)
    db_session.commit()
```

---

### 4.3 数据存储模块

#### 4.3.1 功能描述

负责数据的持久化存储，包括结构化数据和向量索引。

#### 4.3.2 数据库表设计

**新闻表 (news)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| title | VARCHAR(500) | 标题 |
| content | TEXT | 正文 |
| abstract | TEXT | 摘要 |
| publish_time | TIMESTAMP | 发布时间 |
| source | VARCHAR(100) | 来源 |
| detail_url | VARCHAR(500) | 原文链接 |
| crawler | VARCHAR(50) | 爬虫标识 |
| matched_keywords | JSONB | 匹配的关键词 |
| embedding | vector(1024) | 向量表示 |
| is_representative | BOOLEAN | 是否为事件代表新闻 |
| event_id | INTEGER | 关联事件ID |
| created_at | TIMESTAMP | 创建时间 |

**事件表 (event)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| event_type | VARCHAR(50) | 事件类型 |
| title | VARCHAR(500) | 事件标题（代表新闻标题） |
| summary | TEXT | 事件摘要（代表新闻摘要） |
| centroid_embedding | vector(1024) | 中心向量 |
| news_count | INTEGER | 关联新闻数 |
| representative_news_id | INTEGER | 代表新闻ID |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**公司表 (companies)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| name | VARCHAR(200) | 公司名称 |
| name_en | VARCHAR(200) | 英文名称 |

**药物表 (drugs)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| name | VARCHAR(200) | 药物名称 |
| generic_name | VARCHAR(200) | 通用名 |
| mechanism_of_action | TEXT | 作用机制 |
| indication | TEXT | 适应症 |

**药物研发进度表 (drug_development_event)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| drug_id | INTEGER | 药物ID |
| company_id | INTEGER | 公司ID |
| development_stage | VARCHAR(50) | 研发阶段 |
| indication | TEXT | 适应症 |
| update_date | DATE | 更新日期 |

**Watchlist表 (watchlist)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| user_id | INTEGER | 用户ID |
| entity_type | VARCHAR(50) | 实体类型(drug/company/keyword) |
| entity_name | VARCHAR(200) | 实体名称 |
| email | VARCHAR(200) | 通知邮箱 |
| enabled | BOOLEAN | 是否启用 |
| created_at | TIMESTAMP | 创建时间 |

**爬虫任务记录表 (crawler_task)：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| crawler_name | VARCHAR(50) | 爬虫名称 |
| start_time | TIMESTAMP | 开始时间 |
| end_time | TIMESTAMP | 结束时间 |
| status | VARCHAR(20) | 状态(running/success/failed) |
| total_count | INTEGER | 抓取总数 |
| success_count | INTEGER | 成功数 |
| error_message | TEXT | 错误信息 |

#### 4.3.3 向量索引

```sql
-- 创建向量索引（IVFFlat）
CREATE INDEX ON news USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 向量检索函数
CREATE OR REPLACE FUNCTION search_similar_news(
    query_embedding vector(1024),
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    id INTEGER,
    title VARCHAR(500),
    abstract TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        n.id,
        n.title,
        n.abstract,
        1 - (n.embedding <=> query_embedding) as similarity
    FROM news n
    ORDER BY n.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;
```

---

### 4.4 事件聚类模块

#### 4.4.1 功能描述

将入库的 raw_data（新闻）通过向量相似度聚集成事件簇，每个事件簇选择一条代表新闻用于前端展示。

#### 4.4.2 聚类流程

```
raw_data新闻 → 向量相似度计算 → 事件聚类 → 选择代表新闻 → 更新事件表
```

#### 4.4.3 聚类算法

**基于相似度阈值的链式聚类：**

```python
class EventClusterer:
    def __init__(
        self,
        threshold_high: float = 0.85,  # 高相似度阈值
        threshold_mid: float = 0.75,   # 中相似度阈值
        threshold_low: float = 0.65,   # 低相似度阈值
    ):
        self.threshold_high = threshold_high
        self.threshold_mid = threshold_mid
        self.threshold_low = threshold_low
    
    def cluster(self, news_list: List[News]) -> List[Event]:
        """对新闻进行事件聚类"""
        events = []
        unassigned = list(news_list)
        
        while unassigned:
            # 取第一条新闻作为种子
            seed = unassigned.pop(0)
            event = self._create_event(seed)
            
            # 寻找相似新闻
            i = 0
            while i < len(unassigned):
                news = unassigned[i]
                similarity = self._compute_similarity(seed.embedding, news.embedding)
                
                if similarity >= self.threshold_high:
                    # 高相似度，直接加入事件
                    event.news_ids.append(news.id)
                    unassigned.pop(i)
                elif similarity >= self.threshold_mid:
                    # 中相似度，检查与事件中心向量的相似度
                    centroid = self._compute_centroid(event)
                    if self._compute_similarity(centroid, news.embedding) >= self.threshold_mid:
                        event.news_ids.append(news.id)
                        unassigned.pop(i)
                    else:
                        i += 1
                else:
                    i += 1
            
            events.append(event)
        
        return events
    
    def _compute_similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """计算余弦相似度"""
        return cosine_similarity([emb1], [emb2])[0][0]
    
    def _compute_centroid(self, event: Event) -> List[float]:
        """计算事件中心向量"""
        embeddings = [self._get_news_embedding(nid) for nid in event.news_ids]
        return np.mean(embeddings, axis=0).tolist()
```

#### 4.4.4 代表新闻选择

**选择策略：**

```python
def select_representative_news(event: Event, news_dict: Dict[int, News]) -> News:
    """选择事件的代表新闻"""
    # 计算事件中心向量
    embeddings = [news_dict[nid].embedding for nid in event.news_ids]
    centroid = np.mean(embeddings, axis=0)
    
    # 选择最接近中心向量的新闻
    best_news = None
    best_similarity = -1
    
    for nid in event.news_ids:
        news = news_dict[nid]
        similarity = cosine_similarity([centroid], [news.embedding])[0][0]
        if similarity > best_similarity:
            best_similarity = similarity
            best_news = news
    
    return best_news
```

#### 4.4.5 事件更新逻辑

**增量更新：**

```python
def update_event_with_news(event: Event, new_news: News):
    """将新新闻加入已有事件"""
    # 计算新新闻与事件中心向量的相似度
    similarity = cosine_similarity(
        [event.centroid_embedding], 
        [new_news.embedding]
    )[0][0]
    
    if similarity >= 0.7:  # 阈值
        # 加入事件
        event.news_ids.append(new_news.id)
        event.news_count += 1
        
        # 更新中心向量（加权平均）
        alpha = 0.1  # 新新闻权重
        event.centroid_embedding = (
            (1 - alpha) * np.array(event.centroid_embedding) +
            alpha * np.array(new_news.embedding)
        ).tolist()
        
        # 检查是否需要更换代表新闻
        current_rep = get_news(event.representative_news_id)
        if new_news.publish_time > current_rep.publish_time:
            # 新新闻更新，可能成为新代表
            event.representative_news_id = new_news.id
            event.title = new_news.title
            event.summary = new_news.abstract
```

#### 4.4.6 前端展示逻辑

**事件列表页：**
- 展示所有事件的代表新闻
- 显示每个事件关联的新闻数量

**事件详情页：**
- 左侧：代表新闻完整内容
- 右侧边栏：同事件簇下的其他新闻列表

```python
@app.get("/events/{event_id}")
async def get_event_detail(event_id: int):
    event = db.query(Event).get(event_id)
    representative = db.query(News).get(event.representative_news_id)
    related_news = db.query(News).filter(
        News.event_id == event_id,
        News.id != event.representative_news_id
    ).all()
    
    return {
        "event": event,
        "representative_news": representative,
        "related_news": related_news
    }
```

---

### 4.5 RAG智慧问答模块

#### 4.5.1 功能描述

基于检索增强生成（RAG）技术，提供智能问答服务。支持多轮对话，能够结合新闻知识库和通用知识回答用户问题。

#### 4.5.2 核心流程

```
用户提问 → 意图识别 → 检索策略选择 → 向量检索 → 重排序 → 上下文构建 → LLM生成 → 答案输出
                ↓
         对话历史管理 ← 上下文维护 ← 多轮对话支持
```

#### 4.5.3 意图识别

**意图分类：**

| 意图类型 | 说明 | 示例 |
|----------|------|------|
| `news_query` | 查询特定新闻 | "最近关于司美格鲁肽的新闻" |
| `drug_info` | 药物信息查询 | "司美格鲁肽是什么药" |
| `company_query` | 公司动态查询 | "诺和诺德最近有什么动态" |
| `general` | 通用问题 | "什么是GLP-1受体激动剂" |
| `comparison` | 对比问题 | "司美格鲁肽和度拉糖肽有什么区别" |

**实现逻辑：**

```python
INTENT_PROMPT = """分析用户问题的意图，从以下类型中选择：
- news_query: 查询新闻
- drug_info: 药物信息
- company_query: 公司信息
- general: 通用知识
- comparison: 对比问题

用户问题：{question}

只返回意图类型，不要解释："""

def classify_intent(question: str) -> str:
    response = llm.generate(INTENT_PROMPT.format(question=question))
    return response.strip().lower()
```

#### 4.5.4 检索策略

**混合检索流程：**

```python
class RAGRetriever:
    def retrieve(self, query: str, intent: str, top_k: int = 10) -> List[Document]:
        # 1. 生成查询向量
        query_embedding = self.embedding_model.encode(query)
        
        # 2. 向量检索
        vector_results = self.vector_search(query_embedding, top_k=top_k*2)
        
        # 3. 全文检索（针对news_query意图）
        if intent == "news_query":
            text_results = self.fulltext_search(query, top_k=top_k*2)
            # 融合结果
            results = self.hybrid_fusion(vector_results, text_results)
        else:
            results = vector_results
        
        # 4. 重排序
        results = self.rerank(query, results)
        
        return results[:top_k]
    
    def hybrid_fusion(
        self, 
        vector_results: List[Document], 
        text_results: List[Document],
        alpha: float = 0.6
    ) -> List[Document]:
        """RRF融合算法"""
        scores = {}
        k = 60
        
        for i, doc in enumerate(vector_results):
            scores[doc.id] = scores.get(doc.id, 0) + alpha / (k + i + 1)
        
        for i, doc in enumerate(text_results):
            scores[doc.id] = scores.get(doc.id, 0) + (1 - alpha) / (k + i + 1)
        
        all_docs = {doc.id: doc for doc in vector_results + text_results}
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        return [all_docs[doc_id] for doc_id in sorted_ids]
```

#### 4.5.5 重排序

```python
class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model = CrossEncoder(model_name)
    
    def rerank(
        self, 
        query: str, 
        documents: List[Document], 
        top_k: int = 10
    ) -> List[Document]:
        """基于Cross-Encoder重排序"""
        pairs = [(query, doc.content) for doc in documents]
        scores = self.model.predict(pairs)
        
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        return [doc for doc, score in scored_docs[:top_k]]
```

#### 4.5.6 多轮对话管理

**对话历史存储：**

```python
@dataclass
class ConversationTurn:
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime

class ConversationManager:
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.conversations: Dict[str, List[ConversationTurn]] = {}
    
    def add_turn(self, session_id: str, role: str, content: str):
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        self.conversations[session_id].append(
            ConversationTurn(role=role, content=content, timestamp=datetime.now())
        )
        
        # 限制历史长度
        if len(self.conversations[session_id]) > self.max_history:
            self.conversations[session_id] = self.conversations[session_id][-self.max_history:]
    
    def get_history(self, session_id: str) -> List[ConversationTurn]:
        return self.conversations.get(session_id, [])
```

#### 4.5.7 提示词工程

**系统提示词：**

```python
SYSTEM_PROMPT = """你是DrugIntel.ai的医药情报助手，专注于医药行业信息查询和分析。

你的能力：
1. 查询和分析医药新闻动态
2. 提供药物研发进度信息
3. 解答医药行业相关问题
4. 对比分析不同药物或公司

回答原则：
- 基于检索到的新闻资料回答，并在回答中标注来源
- 如果检索资料不足以回答问题，明确告知用户
- 保持回答专业、准确、简洁
- 对于通用知识问题，可以结合检索资料和自身知识回答

当前对话上下文：
{context}
"""

def build_prompt(
    question: str, 
    documents: List[Document], 
    history: List[ConversationTurn]
) -> str:
    # 构建上下文
    context = "\n\n".join([
        f"【新闻{i+1}】{doc.title}\n{doc.abstract}"
        for i, doc in enumerate(documents)
    ])
    
    # 构建历史对话
    history_text = "\n".join([
        f"{'用户' if h.role == 'user' else '助手'}: {h.content}"
        for h in history[-5:]  # 最近5轮
    ])
    
    prompt = f"""{SYSTEM_PROMPT.format(context=context)}

历史对话：
{history_text}

用户问题：{question}

请基于以上信息回答："""
    
    return prompt
```

#### 4.5.8 API接口

**POST /chat**

请求体：
```json
{
    "session_id": "user_123_session_456",
    "question": "最近关于司美格鲁肽有什么新闻？",
    "stream": false
}
```

响应体：
```json
{
    "answer": "根据最近的新闻报道，诺和诺德的司美格鲁肽...",
    "sources": [
        {
            "id": 123,
            "title": "诺和诺德公布司美格鲁肽新适应症临床试验结果",
            "url": "https://...",
            "relevance_score": 0.92
        }
    ],
    "intent": "news_query",
    "created_at": "2026-03-26T10:30:00Z"
}
```

**WebSocket /ws/chat**

支持流式输出：
```javascript
ws.send(JSON.stringify({
    "session_id": "user_123",
    "question": "司美格鲁肽是什么药？"
}));

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // data.type: "token" | "sources" | "done"
    // data.content: 文本片段或来源列表
};
```

---

### 4.5 搜索与检索模块

#### 4.5.1 功能描述

提供多维度新闻检索能力，作为 RAG 模块的底层检索能力，同时也支持前端直接调用。

**主要用途：**
1. **RAG 模块调用**：为智能问答提供相关新闻检索
2. **前端直接调用**：用户通过搜索框查询新闻

#### 4.5.2 搜索类型

| 搜索类型 | 说明 | 适用场景 |
|----------|------|----------|
| 全文搜索 | 基于关键词的文本匹配 | 精确查找特定内容 |
| 向量检索 | 基于语义相似度 | 模糊查询、语义相关 |
| 混合搜索 | 结合全文和向量 | 综合查询 |

#### 4.5.3 全文搜索实现

```python
def fulltext_search(
    query: str,
    filters: dict = None,
    limit: int = 20,
    offset: int = 0
) -> Tuple[List[News], int]:
    """全文搜索"""
    sql = """
        SELECT n.*, ts_rank(n.search_vector, plainto_tsquery('chinese', :query)) as rank
        FROM news n
        WHERE n.search_vector @@ plainto_tsquery('chinese', :query)
    """
    
    params = {"query": query}
    
    if filters:
        if filters.get("start_date"):
            sql += " AND n.publish_time >= :start_date"
            params["start_date"] = filters["start_date"]
        if filters.get("end_date"):
            sql += " AND n.publish_time <= :end_date"
            params["end_date"] = filters["end_date"]
        if filters.get("source"):
            sql += " AND n.source = :source"
            params["source"] = filters["source"]
    
    sql += " ORDER BY rank DESC, n.publish_time DESC"
    sql += f" LIMIT {limit} OFFSET {offset}"
    
    results = db.execute(sql, params).fetchall()
    
    # 获取总数
    count_sql = sql.split("ORDER BY")[0].replace("SELECT n.*, ts_rank...", "SELECT COUNT(*)")
    total = db.execute(count_sql, params).scalar()
    
    return results, total
```

#### 4.5.4 向量检索实现

```python
def vector_search(
    query: str,
    limit: int = 10,
    threshold: float = 0.5
) -> List[News]:
    """向量检索"""
    query_embedding = embedding_manager.encode_single(query)
    
    sql = """
        SELECT n.id, n.title, n.abstract, n.detail_url,
               1 - (n.embedding <=> :embedding) as similarity
        FROM news n
        WHERE 1 - (n.embedding <=> :embedding) > :threshold
        ORDER BY n.embedding <=> :embedding
        LIMIT :limit
    """
    
    results = db.execute(sql, {
        "embedding": str(query_embedding),
        "threshold": threshold,
        "limit": limit
    }).fetchall()
    
    return results
```

#### 4.5.5 API接口

**GET /news**

查询参数：
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| title_keyword | string | 否 | 标题关键词 |
| keyword | string | 否 | 全文关键词 |
| source | string | 否 | 来源筛选 |
| start_date | string | 否 | 开始日期 YYYY-MM-DD |
| end_date | string | 否 | 结束日期 YYYY-MM-DD |
| limit | integer | 否 | 每页数量，默认20 |
| offset | integer | 否 | 偏移量，默认0 |

**POST /search/vector**

请求体：
```json
{
    "query": "司美格鲁肽的临床试验结果",
    "top_k": 10,
    "threshold": 0.5
}
```

---

### 4.6 告警通知模块

#### 4.6.1 功能描述

支持用户订阅关注的药物、公司或关键词，当有相关新闻时自动发送邮件通知。

#### 4.6.2 告警流程

```
新新闻入库 → 匹配Watchlist规则 → 生成告警内容 → 发送邮件通知
```

#### 4.6.3 Watchlist管理

**添加订阅：**

```python
def add_watchlist(
    user_id: int,
    entity_type: str,  # "drug", "company", "keyword"
    entity_name: str,
    email: str
) -> Watchlist:
    watchlist = Watchlist(
        user_id=user_id,
        entity_type=entity_type,
        entity_name=entity_name,
        email=email,
        enabled=True
    )
    db.add(watchlist)
    db.commit()
    return watchlist
```

**匹配规则：**

```python
def match_watchlist(news: News) -> List[Watchlist]:
    """检查新闻是否匹配任何Watchlist"""
    matched = []
    
    watchlists = db.query(Watchlist).filter(Watchlist.enabled == True).all()
    
    for wl in watchlists:
        if wl.entity_type == "keyword":
            if wl.entity_name in news.title or wl.entity_name in news.content:
                matched.append(wl)
        elif wl.entity_type == "drug":
            # 查询药物关联
            if is_drug_in_news(wl.entity_name, news):
                matched.append(wl)
        elif wl.entity_type == "company":
            if is_company_in_news(wl.entity_name, news):
                matched.append(wl)
    
    return matched
```

#### 4.6.4 邮件推送

**邮件模板：**

```html
<h2>DrugIntel.ai 情报通知</h2>

<p>您关注的「{entity_name}」有新动态：</p>

<div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0;">
    <h3>{news_title}</h3>
    <p><strong>来源：</strong>{source}</p>
    <p><strong>时间：</strong>{publish_time}</p>
    <p><strong>摘要：</strong>{abstract}</p>
    <a href="{detail_url}">查看原文</a>
</div>

<p>
    <a href="{unsubscribe_url}">取消订阅</a> | 
    <a href="{dashboard_url}">管理订阅</a>
</p>
```

**发送逻辑：**

```python
class EmailSender:
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
    
    def send_alert(self, to_email: str, news: News, entity_name: str):
        subject = f"【DrugIntel】{entity_name}相关动态：{news.title}"
        html_content = render_template("alert_email.html", 
            news=news, entity_name=entity_name)
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.username
        msg['To'] = to_email
        msg.attach(MIMEText(html_content, 'html'))
        
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.username, to_email, msg.as_string())
```

#### 4.6.5 API接口

**POST /watchlist**

请求体：
```json
{
    "entity_type": "drug",
    "entity_name": "司美格鲁肽",
    "email": "user@example.com"
}
```

**GET /watchlist**

响应体：
```json
{
    "items": [
        {
            "id": 1,
            "entity_type": "drug",
            "entity_name": "司美格鲁肽",
            "email": "user@example.com",
            "enabled": true,
            "created_at": "2026-03-26T10:00:00Z"
        }
    ]
}
```

**DELETE /watchlist/{id}**

---

### 4.7 核心数据展示

#### 4.7.1 功能描述

在前端页面展示关键统计指标，包括研发进度统计、新闻趋势等。

#### 4.7.2 统计指标

| 指标 | 说明 | 数据来源 |
|------|------|----------|
| 研发阶段分布 | 各阶段药物数量 | drug_development_event |
| 新闻来源分布 | 各来源新闻数量 | news |
| 每日新闻趋势 | 近7天/30天新闻量 | news |
| 热门关键词 | 高频关键词TOP10 | news.matched_keywords |
| 最新事件 | 最近事件列表 | event |

#### 4.7.3 数据接口

**GET /stats/overview**

响应体：
```json
{
    "total_news": 1523,
    "total_events": 89,
    "total_drugs": 234,
    "total_companies": 156,
    "news_today": 45,
    "events_this_week": 12
}
```

**GET /stats/development-stages**

响应体：
```json
{
    "preclinical": 45,
    "IND": 23,
    "phase1": 67,
    "phase2": 89,
    "phase3": 34,
    "NDA": 12,
    "BLA": 5,
    "approved": 8
}
```

**GET /stats/news-trend**

查询参数：
- `days`: 天数，默认7

响应体：
```json
{
    "dates": ["2026-03-20", "2026-03-21", ...],
    "counts": [45, 52, 38, 61, 55, 48, 50]
}
```

#### 4.7.4 前端展示

在首页/仪表盘页面展示：
- 顶部卡片：总数统计
- 饼图：研发阶段分布
- 折线图：新闻趋势
- 列表：最新事件

---

### 4.8 轻量级监控

#### 4.8.1 功能描述

提供爬虫运行状态、数据处理状态和系统健康状态的监控页面。

#### 4.8.2 爬虫监控

**监控指标：**

| 指标 | 说明 |
|------|------|
| 运行状态 | running / success / failed |
| 本次抓取数 | 当前任务抓取的新闻数量 |
| 成功率 | 成功抓取数 / 总抓取数 |
| 最近运行时间 | 上次任务完成时间 |
| 错误信息 | 失败时的错误详情 |

**数据采集：**

```python
class CrawlerMonitor:
    def record_task_start(self, crawler_name: str) -> int:
        task = CrawlerTask(
            crawler_name=crawler_name,
            start_time=datetime.now(),
            status="running"
        )
        db.add(task)
        db.commit()
        return task.id
    
    def record_task_end(
        self, 
        task_id: int, 
        status: str, 
        total_count: int, 
        success_count: int,
        error_message: str = None
    ):
        task = db.query(CrawlerTask).get(task_id)
        task.end_time = datetime.now()
        task.status = status
        task.total_count = total_count
        task.success_count = success_count
        task.error_message = error_message
        db.commit()
    
    def get_crawler_status(self, crawler_name: str) -> dict:
        latest_task = db.query(CrawlerTask).filter(
            CrawlerTask.crawler_name == crawler_name
        ).order_by(CrawlerTask.start_time.desc()).first()
        
        return {
            "crawler_name": crawler_name,
            "status": latest_task.status if latest_task else "never_run",
            "last_run": latest_task.end_time if latest_task else None,
            "total_count": latest_task.total_count if latest_task else 0,
            "success_count": latest_task.success_count if latest_task else 0,
            "success_rate": latest_task.success_count / latest_task.total_count 
                if latest_task and latest_task.total_count > 0 else 0,
            "error_message": latest_task.error_message if latest_task else None
        }
```

#### 4.8.3 数据处理监控

**监控指标：**

| 指标 | 说明 |
|------|------|
| 待处理队列 | Redis队列中待处理的新闻数 |
| 处理成功率 | 成功处理数 / 总处理数 |
| 平均处理时间 | 每条新闻的平均处理耗时 |

**实现：**

```python
class ProcessingMonitor:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def get_queue_length(self) -> int:
        return self.redis.llen("news_processing_queue")
    
    def record_processing(self, success: bool, duration_ms: int):
        self.redis.incr("processing_total")
        if success:
            self.redis.incr("processing_success")
        self.redis.lpush("processing_times", duration_ms)
        self.redis.ltrim("processing_times", 0, 999)  # 保留最近1000条
    
    def get_stats(self) -> dict:
        total = int(self.redis.get("processing_total") or 0)
        success = int(self.redis.get("processing_success") or 0)
        times = [int(t) for t in self.redis.lrange("processing_times", 0, -1)]
        
        return {
            "queue_length": self.get_queue_length(),
            "total_processed": total,
            "success_rate": success / total if total > 0 else 0,
            "avg_processing_time_ms": sum(times) / len(times) if times else 0
        }
```

#### 4.8.4 系统状态

**健康检查：**

```python
@app.get("/health")
async def health_check():
    checks = {}
    
    # 数据库检查
    try:
        db.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
    
    # Redis检查
    try:
        redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
    
    # 向量索引检查
    try:
        db.execute("SELECT COUNT(*) FROM news WHERE embedding IS NOT NULL")
        checks["vector_index"] = "ok"
    except Exception as e:
        checks["vector_index"] = f"error: {str(e)}"
    
    all_ok = all(v == "ok" for v in checks.values())
    
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now().isoformat()
    }
```

#### 4.8.5 API接口

**GET /monitor/crawlers**

响应体：
```json
{
    "crawlers": [
        {
            "name": "bioon",
            "status": "success",
            "last_run": "2026-03-26T08:00:00Z",
            "total_count": 50,
            "success_count": 48,
            "success_rate": 0.96
        },
        {
            "name": "globenewswire",
            "status": "running",
            "last_run": null,
            "total_count": 0,
            "success_count": 0,
            "success_rate": 0
        }
    ]
}
```

**GET /monitor/processing**

响应体：
```json
{
    "queue_length": 12,
    "total_processed": 1523,
    "success_rate": 0.98,
    "avg_processing_time_ms": 2500
}
```

**GET /monitor/system**

响应体：
```json
{
    "status": "ok",
    "checks": {
        "database": "ok",
        "redis": "ok",
        "vector_index": "ok"
    },
    "uptime_seconds": 86400,
    "version": "1.0.0"
}
```

---

### 4.9 API服务模块

#### 4.9.1 功能描述

提供统一的RESTful API接口，支持所有业务功能的访问。

#### 4.9.2 API列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查 |
| GET | /news | 新闻列表 |
| GET | /news/{id} | 新闻详情 |
| GET | /events/{id}/news | 事件相关新闻 |
| POST | /search/vector | 向量检索 |
| POST | /chat | RAG问答 |
| GET | /watchlist | Watchlist列表 |
| POST | /watchlist | 添加Watchlist |
| DELETE | /watchlist/{id} | 删除Watchlist |
| GET | /stats/overview | 统计概览 |
| GET | /stats/development-stages | 研发阶段统计 |
| GET | /stats/news-trend | 新闻趋势 |
| GET | /monitor/crawlers | 爬虫监控 |
| GET | /monitor/processing | 处理监控 |
| GET | /monitor/system | 系统状态 |
| GET | /drug-rd-progress | 药物研发进度 |
| GET | /drug-rd-progress/stats | 研发进度统计 |

#### 4.9.3 统一响应格式

**成功响应：**

```json
{
    "data": { ... },
    "message": "success"
}
```

**分页响应：**

```json
{
    "total": 100,
    "items": [ ... ],
    "limit": 20,
    "offset": 0
}
```

**错误响应：**

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "参数验证失败",
        "details": {
            "field": "start_date",
            "reason": "日期格式错误"
        }
    }
}
```

#### 4.9.4 错误码定义

| 错误码 | HTTP状态码 | 说明 |
|--------|------------|------|
| VALIDATION_ERROR | 400 | 参数验证失败 |
| NOT_FOUND | 404 | 资源不存在 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |
| SERVICE_UNAVAILABLE | 503 | 服务暂时不可用 |

---

### 4.10 前端应用模块

#### 4.10.1 功能描述

提供用户交互界面，包括新闻浏览、搜索、问答、告警管理等功能。

#### 4.10.2 页面结构

| 页面 | 路由 | 功能 |
|------|------|------|
| 首页 | / | 统计概览、快捷入口 |
| 新闻列表 | /news | 新闻浏览、搜索筛选 |
| 新闻详情 | /news/:id | 新闻详情、相关推荐 |
| RAG问答 | /chat | 智能问答界面 |
| 告警管理 | /watchlist | Watchlist管理 |
| 系统监控 | /monitor | 爬虫、处理状态 |
| 研发进度 | /drug-rd | 药物研发进度查询 |

#### 4.10.3 组件设计

**核心组件：**

| 组件 | 说明 |
|------|------|
| NewsList | 新闻列表组件 |
| NewsCard | 新闻卡片组件 |
| SearchBar | 搜索栏组件 |
| ChatWindow | 问答对话窗口 |
| WatchlistItem | Watchlist条目组件 |
| StatsCard | 统计卡片组件 |
| TrendChart | 趋势图表组件 |
| CrawlerStatus | 爬虫状态组件 |

#### 4.10.4 路由配置

```typescript
const routes = [
    { path: '/', component: HomePage },
    { path: '/news', component: NewsListPage },
    { path: '/news/:id', component: NewsDetailPage },
    { path: '/chat', component: ChatPage },
    { path: '/watchlist', component: WatchlistPage },
    { path: '/monitor', component: MonitorPage },
    { path: '/drug-rd', component: DrugRDPage },
];
```

---

## 5. 数据模型设计

### 5.1 ER图

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Company   │       │    Drug     │       │    News     │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id          │       │ id          │       │ id          │
│ name        │◄──────│ name        │       │ title       │
│ name_en     │       │ generic_name│       │ content     │
│ country     │       │ mechanism   │       │ abstract    │
└─────────────┘       │ indication  │       │ embedding   │
                      └──────┬──────┘       │ event_id    │◄────┐
                             │              └─────────────┘     │
                             │                                  │
                      ┌──────┴──────┐                          │
                      │DrugCompany  │                          │
                      ├─────────────┤                          │
                      │ drug_id     │                          │
                      │ company_id  │                          │
                      └─────────────┘                          │
                                                               │
┌─────────────┐       ┌─────────────┐                          │
│   Event     │       │DrugDevEvent │                          │
├─────────────┤       ├─────────────┤                          │
│ id          │◄──────│ id          │                          │
│ event_type  │       │ drug_id     │                          │
│ title       │       │ company_id  │                          │
│ summary     │       │ stage       │                          │
│ centroid_emb│       │ indication  │                          │
│ news_count  │       └─────────────┘                          │
└──────┬──────┘                                                 │
       │                                                        │
       └────────────────────────────────────────────────────────┘

┌─────────────┐       ┌─────────────┐
│  Watchlist  │       │ CrawlerTask │
├─────────────┤       ├─────────────┤
│ id          │       │ id          │
│ user_id     │       │ crawler_name│
│ entity_type │       │ start_time  │
│ entity_name │       │ end_time    │
│ email       │       │ status      │
│ enabled     │       │ total_count │
└─────────────┘       │ success_cnt │
                      └─────────────┘
```

### 5.2 表结构定义

详见 [4.3 数据存储模块](#43-数据存储模块)

### 5.3 向量索引设计

| 索引名称 | 表 | 字段 | 类型 | 参数 |
|----------|-----|------|------|------|
| news_embedding_idx | news | embedding | ivfflat | lists=100 |
| event_centroid_idx | event | centroid_embedding | ivfflat | lists=50 |

---

## 6. API接口规范

### 6.1 RESTful API列表

详见 [4.10 API服务模块](#410-api服务模块)

### 6.2 请求/响应格式

#### 6.2.1 请求头

```
Content-Type: application/json
Accept: application/json
```

#### 6.2.2 响应头

```
Content-Type: application/json
X-API-Version: 1.0.0
X-Request-ID: uuid
```

### 6.3 错误码定义

详见 [4.10.4 错误码定义](#4104-错误码定义)

### 6.4 WebSocket接口

**连接地址：** `ws://localhost:8000/ws/chat`

**消息格式：**

```json
{
    "type": "token" | "sources" | "done" | "error",
    "content": "...",
    "timestamp": "2026-03-26T10:30:00Z"
}
```

---

## 7. 非功能需求

### 7.1 性能需求

| 指标 | 要求 |
|------|------|
| API响应时间 | P95 < 500ms |
| 向量检索 | < 200ms (10万数据) |
| 新闻列表查询 | < 100ms |
| RAG问答响应 | < 5s (首字输出) |
| 并发用户数 | 支持10并发 |

### 7.2 安全需求

| 需求 | 说明 |
|------|------|
| 输入验证 | 所有输入参数进行类型和格式验证 |
| SQL注入防护 | 使用ORM参数化查询 |
| XSS防护 | 前端输出转义 |
| 敏感信息保护 | API Key等配置不暴露在代码中 |

### 7.3 可用性需求

| 需求 | 说明 |
|------|------|
| 错误处理 | 所有异常捕获并返回友好错误信息 |
| 日志记录 | 关键操作记录日志 |
| 健康检查 | 提供健康检查接口 |
| 数据备份 | 支持数据库备份 |

### 7.4 兼容性需求

| 类型 | 要求 |
|------|------|
| 浏览器 | Chrome 90+, Firefox 88+, Safari 14+ |
| Python版本 | 3.10+ |
| Node.js版本 | 18+ |
| PostgreSQL版本 | 15+ |

---

## 8. 验收标准

### 8.1 功能验收清单

| 模块 | 功能点 | 验收标准 |
|------|--------|----------|
| 数据采集 | 爬虫运行 | 能够成功抓取新闻并入库 |
| 数据处理 | 摘要生成 | 摘要长度150-200字，内容准确 |
| 数据处理 | 向量生成 | 向量维度1024，归一化 |
| 数据处理 | 去重 | 重复新闻过滤率>90% |
| RAG问答 | 意图识别 | 准确率>85% |
| RAG问答 | 多轮对话 | 支持上下文追问 |
| RAG问答 | 答案质量 | 相关性评分>0.7 |
| 搜索检索 | 全文搜索 | 支持中文分词 |
| 搜索检索 | 向量检索 | Top10召回率>80% |
| 告警通知 | 邮件推送 | 匹配后5分钟内发送 |
| 核心数据展示 | 统计指标 | 数据准确，实时更新 |
| 轻量级监控 | 状态展示 | 实时反映系统状态 |

### 8.2 性能验收指标

| 指标 | 目标值 | 测试方法 |
|------|--------|----------|
| API响应时间 | P95 < 500ms | 压力测试 |
| 向量检索延迟 | < 200ms | 单元测试 |
| 并发处理 | 10用户无阻塞 | 并发测试 |
| 内存占用 | < 2GB | 监控工具 |

### 8.3 测试用例示例

**测试用例1：RAG问答基本功能**

```
前置条件：数据库中存在司美格鲁肽相关新闻
测试步骤：
1. 发送POST /chat请求，问题为"司美格鲁肽是什么药？"
2. 检查响应中包含答案和来源
预期结果：
- 返回状态码200
- 答案内容与司美格鲁肽相关
- sources列表非空
```

**测试用例2：告警邮件发送**

```
前置条件：已添加Watchlist订阅"司美格鲁肽"
测试步骤：
1. 入库一条包含"司美格鲁肽"的新闻
2. 等待告警任务执行
预期结果：
- 订阅邮箱收到告警邮件
- 邮件内容包含新闻标题和摘要
```

---

## 9. 附录

### 9.1 部署指南

#### 9.1.1 环境要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 15+ (启用pgvector扩展)
- Redis 7+

#### 9.1.2 部署步骤

```bash
# 1. 克隆项目
git clone https://github.com/xxx/drugintel-ai.git
cd drugintel-ai

# 2. 后端配置
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .

# 3. 配置环境变量
cp config/.env.example config/.env
# 编辑.env文件，填入数据库连接、API Key等

# 4. 初始化数据库
python -c "from scripts.database import init_db; init_db()"

# 5. 启动后端
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# 6. 前端配置
cd frontend
npm install
npm run dev
```

#### 9.1.3 Docker部署

```bash
# 使用Docker Compose一键部署
docker-compose up -d
```

### 9.2 环境配置

**config/.env 示例：**

```env
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/drugintel

# Redis配置
REDIS_URL=redis://localhost:6379/0

# LLM配置
SILICONFLOW_API_KEY=your_api_key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1

# 邮件配置
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your_email@example.com
SMTP_PASSWORD=your_password

# 其他配置
ENVIRONMENT=development
DEBUG=true
TIMEZONE=Asia/Shanghai
```

### 9.3 常见问题

**Q1: pgvector扩展未启用怎么办？**

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Q2: 向量检索性能慢怎么办？**

- 确保已创建向量索引
- 调整ivfflat的lists参数
- 考虑使用HNSW索引

**Q3: LLM调用失败怎么办？**

- 检查API Key是否正确
- 检查网络连接
- 查看API调用限制

**Q4: 邮件发送失败怎么办？**

- 检查SMTP配置
- 确认邮箱地址正确
- 查看邮件服务日志

---

## 文档结束

**文档版本：** V1.0  
**最后更新：** 2026-03-26  
**维护者：** 开发团队
