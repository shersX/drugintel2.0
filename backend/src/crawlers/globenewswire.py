#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医药情报AI平台 - globenewswire新闻爬虫模块
用于采集globenewswire新闻列表信息
"""
import asyncio
import json
import time
from urllib.parse import urljoin
from datetime import datetime
from zoneinfo import ZoneInfo
import aiohttp
from bs4 import BeautifulSoup
import os

from typing import List, Dict, Optional
from backend.src.core.logging import get_logger

crawler_name="Globenewswire"
logger = get_logger("globenewswire")

class GlobeNewswireCrawler:
    """Globenewswire新闻爬虫类"""
    
    def __init__(
        self,
        base_url: str = "https://www.globenewswire.com",
        newrooom_url: str = "https://www.globenewswire.com/en/news/heathcare/load/more?page={}&pageSize=10",
        user_agent: Optional[str] = None,
    ):
        """初始化爬虫"""
        self.base_url = base_url
        self.newrooom_url = newrooom_url
        self.et_tz = ZoneInfo("America/New_York")
        self.cn_tz = ZoneInfo("Asia/Shanghai")
        final_user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        # 请求头，供 aiohttp.ClientSession 复用
        self.headers = {
            'User-Agent': final_user_agent,
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }

    def _convert_et_to_china(self, publish_time: str) -> str:
        """
        将 ET 时间字符串转换为中国时间（Asia/Shanghai）
        """
        if not publish_time:
            return publish_time
        cleaned = publish_time.strip()
        tokens = cleaned.split()
        if tokens and tokens[-1] in {"ET", "EST", "EDT"}:
            cleaned = " ".join(tokens[:-1])
        try:
            dt = datetime.strptime(cleaned, "%B %d, %Y %H:%M")
            dt_et = dt.replace(tzinfo=self.et_tz)
            dt_cn = dt_et.astimezone(self.cn_tz)
            return dt_cn.strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            logger.warning("时间转换失败 时间=%s 错误=%s", publish_time, e)
            return publish_time

    async def fetch_news_list(self, session: aiohttp.ClientSession, page_count: int = 1) -> List[Dict]:
        """
        获取多页新闻列表
        
        Args:
            page_count: 需要抓取的页数，从1开始
            
        Returns:
            List[Dict]: 新闻信息列表，包含标题、简介、详细URL等信息
        """
        news_list=[]
        page_count=max(1,page_count)
        base_url=self.base_url.rstrip('/')

        for page in range(1,page_count+1):
            page_url=self.newrooom_url.format(page)
            logger.info("列表抓取中 第%s页 地址=%s", page, page_url)
            async with session.get(page_url, timeout=10) as response:
                response.raise_for_status()
                html = await response.text(encoding='utf-8', errors='ignore')
            
            soup=BeautifulSoup(html,"html.parser")
            for li in soup.select("div.recentNewsH ul li.row"):
                publish_time_raw=li.select_one("div.date-source span").text.strip()
                publish_time=self._convert_et_to_china(publish_time_raw)
                source=li.select_one("div.date-source .sourceLink").text.strip()
                title=li.select_one("div.mainLink a").text.strip()
                detail_url=urljoin(base_url,li.select_one("div.mainLink a")["href"])
                news_list.append({
                    "title":title,
                    "source":source,
                    "publish_time":publish_time,
                    "detail_url":detail_url,
                    "crawler":"globenewswire"
                })
            logger.info("列表页完成 第%s页 条数=%s", page, len(soup.select("div.recentNewsH ul li.row")))
        logger.info("列表抓取完成 页数=%s 总数=%s", page_count, len(news_list))
        return news_list

    async def fetch_news_detail(self, session: aiohttp.ClientSession, news_item: Dict) -> Dict:
        """
        抓取单个新闻详情页面的完整内容
        
        Args:
            news_item: 包含detail_url的新闻项字典
            
        Returns:
            Dict: 更新后的新闻项，包含详情页面的完整内容
        """
        if not news_item.get('detail_url'):
            logger.warning("新闻项缺少详情地址，已跳过 标题=%s", news_item.get('title', '未知标题'))
            return news_item
        
        detail_url = news_item['detail_url']
        try:
            logger.debug("详情抓取中 地址=%s", detail_url)
            async with session.get(detail_url, timeout=10) as response:
                response.raise_for_status()
                html = await response.text(encoding='utf-8', errors='ignore')

            soup=BeautifulSoup(html,"html.parser")
            content_div=soup.find("div",class_="main-body-container")

            if content_div:
                for p in content_div.find_all("p"):
                    # 1. 先清理所有<a>标签内部的换行（用空格合并）
                    for a in p.find_all("a"):
                        # 用空格合并链接内部文本，移除多余空格
                        clean_text = a.get_text(separator=" ", strip=True)
                        a.replace_with(clean_text)
                    
                    # 2. 保留段落边界，但段内用空格连接
                    p_text = p.get_text(separator=" ", strip=True)
                    # 保留段落换行，但段内不加换行
                    # 用临时标记记录段落位置（后续会处理）
                    p.string = p_text
                full_text = content_div.get_text(separator="\n", strip=True)
                news_item['full_text']=full_text

            await asyncio.sleep(0.1)  # 避免单站压力过大            
        except aiohttp.ClientError as e:
            logger.warning("抓取详情页失败 地址=%s 错误=%s", detail_url, e)
        except Exception as e:
            logger.exception("解析详情页失败 地址=%s 错误=%s", detail_url, e)
        return news_item

    async def fetch_all_details(self, session: aiohttp.ClientSession, news_list: List[Dict], concurrency: int = 10) -> List[Dict]:
        """
        批量抓取所有新闻的详情页面（纯异步 + 并发控制）
        
        Args:
            session: aiohttp 会话
            news_list: 新闻列表
            concurrency: 最大并发数
            
        Returns:
            List[Dict]: 更新后的新闻列表，包含详情页面内容
        """
        if not news_list:
            return news_list
        
        total = len(news_list)
        concurrency = max(1, concurrency)
        sem = asyncio.Semaphore(concurrency)
        failed_count = 0
        logger.info("详情抓取开始 总数=%s 并发=%s", total, concurrency)

        async def _wrapped(idx: int, item: Dict):
            nonlocal failed_count
            async with sem:
                try:
                    await self.fetch_news_detail(session, item)
                except Exception as e:
                    failed_count += 1
                    logger.warning("抓取第%s条新闻详情失败 错误=%s", idx, e)

        tasks = [
            asyncio.create_task(_wrapped(idx, news))
            for idx, news in enumerate(news_list, 1)
        ]
        await asyncio.gather(*tasks)

        logger.info("详情抓取完成 总数=%s 失败=%s", total, failed_count)
        return news_list

    def save_to_json(self, news_list: List[Dict], filename: str = f"outjson/{crawler_name}.json"):
        """
        将新闻数据保存为JSON文件
        
        Args:
            news_list: 新闻数据列表
            filename: 保存的文件名
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(news_list, f, ensure_ascii=False, indent=2)
            logger.info("新闻数据已保存 地址=%s", filename)
        except Exception as e:
            logger.exception("保存文件失败 错误=%s", e)

    def print_news_list(self, news_list: List[Dict]):
        """
        打印新闻列表
        
        Args:
            news_list: 新闻数据列表
        """
        logger.info("%s", "="*80)
        logger.info("globenewswire新闻采集结果")
        logger.info("%s", "="*80)
        
        for i, news in enumerate(news_list, 1):
            logger.info("%s. 标题: %s", i, news.get('title', ''))
            logger.info("   日期: %s", news.get('publish_time', ''))
            logger.info(
                "   正文: %s",
                f"{news.get('full_text', '')[:100]}..." if len(news.get('full_text', '')) > 100 else news.get('full_text', ''),
            )
            logger.info("   详细URL: %s", news.get('detail_url', ''))
            logger.info("   %s", "-"*70)
        
        logger.info("总计采集到 %s 条新闻", len(news_list))


async def crawl_globenewswire_async(
    page_count: int = 1,
    fetch_details: bool = False,
    concurrency: int = 10,
    user_agent: Optional[str] = None,
) -> List[Dict]:
    """
    纯异步主函数
    
    Args:
        page_count: 需要抓取的列表页数
        fetch_details: 是否抓取详情页面
        concurrency: 抓取详情时的最大并发数
    """
    crawler = GlobeNewswireCrawler(user_agent=user_agent)
    start_time = time.perf_counter()
    logger.info(
        "采集开始 页数=%s 抓取详情=%s 并发=%s",
        page_count,
        fetch_details,
        concurrency,
    )
    visited_urls=[]
    visited_file = f"outjson/{crawler_name}_url.json"
    #先判断该文件是否存在，然后再读取outjson/GlobeNewswire_visited.json
    if os.path.exists(visited_file):
        with open(visited_file, 'r', encoding='utf-8') as f:
            visited_urls = json.load(f)
    
    async with aiohttp.ClientSession(headers=crawler.headers) as session:
        raw_news_list: List[Dict] = await crawler.fetch_news_list(session, page_count=page_count)
        new_news_list=[news for news in raw_news_list if news['detail_url'] not in visited_urls]
        logger.info(
            "增量过滤完成 原始=%s 过滤=%s 新增=%s",
            len(raw_news_list),
            len(raw_news_list)-len(new_news_list),
            len(new_news_list),
        )

        news_list=[]
        if new_news_list and fetch_details:
            news_list = await crawler.fetch_all_details(session, new_news_list, concurrency=concurrency)

            #爬取完后更新json文件url
            new_urls=[news['detail_url'] for news in raw_news_list if news['detail_url']]
            with open(visited_file,'w',encoding='utf-8') as f:
                json.dump(new_urls,f,ensure_ascii=False,indent=2)
        
        if news_list:
            #crawler.print_news_list(news_list)
            #crawler.save_to_json(news_list)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info("采集完成 总数=%s 耗时=%s毫秒", len(news_list), elapsed_ms)
            return news_list
        else:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info("采集完成 总数=0 耗时=%s毫秒", elapsed_ms)
            return []

if __name__ == "__main__":
    # 示例：抓取前 3 页列表 + 详情页，详情并发数 10
    asyncio.run(crawl_globenewswire_async(page_count=1, fetch_details=True, concurrency=3))
