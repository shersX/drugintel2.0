# DrugIntel.ai（当前开发基线）

医药情报采集项目，当前已完成任务 1（数据采集模块）的核心能力：

- 多源爬虫：`bioon` / `globenewswire` / `prnewswire`
- 注册表统一调度：`backend/src/crawlers/registry.py`
- 注册表统一重试：所有异常最多重试 3 次（含退避）
- User-Agent 轮换：在注册表层统一分配并透传到各爬虫
- 统一入口：`main.py` 通过注册表启动全部已启用爬虫
- 联网测试：`tests/test_registry_live_crawlers.py`

## 项目结构（与采集相关）

- `backend/src/crawlers/base_async_crawler.py`：异步爬虫基类（增量过滤、并发详情抓取）
- `backend/src/crawlers/bioon.py`：Bioon 爬虫
- `backend/src/crawlers/globenewswire.py`：GlobeNewswire 爬虫
- `backend/src/crawlers/prnewswire.py`：PRNewswire 爬虫
- `backend/src/crawlers/registry.py`：爬虫注册表、统一重试、UA 轮换
- `tests/test_registry_live_crawlers.py`：注册表统一联网测试
- `outjson/*_url.json`：增量去重 URL 文件

## 环境要求

- Python `>=3.10`
- 建议使用虚拟环境

使用 `uv` 初始化并同步依赖：

```bash
uv init
uv sync
```

## 快速开始

### 1) 通过主入口启动所有爬虫

```bash
python main.py
```

默认参数（在 `main.py` 中）：

- `page_count=2`
- `fetch_details=True`
- `concurrency=3`

### 2) 运行注册表联网测试

```bash
python tests/test_registry_live_crawlers.py
```

说明：

- 该测试会先重置 `outjson/*_url.json`，避免增量去重导致“0 条新增”误判。
- 测试会真实联网，结果受目标站稳定性影响。

## 日志与行为说明

- 注册表日志名：`crawler.registry`
- 爬虫日志名：`bioon` / `globenewswire` / `prnewswire`
- 当某个爬虫执行异常时，注册表会统一重试（最多 3 次）
- 若仍失败，汇总会输出“部分失败”信息及失败爬虫详情

## 当前约定（协作规则）

- 进度文档 `IMPLEMENTATION_PLAN.md` 的任务勾选需先经用户明确许可。
- 当前项目使用 `[√]` 作为完成标记风格。
