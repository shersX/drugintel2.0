#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医药情报AI平台 - Bioon新闻爬虫模块
用于采集news.bioon.com新闻列表信息
"""

import json
import os
import asyncio
import time
from typing import List, Dict, Optional
import re
import aiohttp
from bs4 import BeautifulSoup
from backend.src.core.logging import get_logger
from backend.src.crawlers.base_async_crawler import BaseAsyncCrawler

crawler_name="BioonNews"
logger = get_logger("bioon")
class BioonNewsCrawler(BaseAsyncCrawler):
    """Bioon新闻爬虫类"""
    
    def __init__(self, base_url: str = "https://news.bioon.com", user_agent: Optional[str] = None):
        """初始化爬虫"""
        self.base_url = base_url
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
    
    async def fetch_news_list(self, session: aiohttp.ClientSession, page_count: int = 1) -> List[Dict]:
        """
        获取多页新闻列表
        
        Args:
            page_count: 需要抓取的页数，从1开始
            
        Returns:
            List[Dict]: 新闻信息列表，包含标题、简介、详细URL等信息
        """
        news_list: List[Dict] = []
        page_count = max(1, page_count)
        
        base = self.base_url.rstrip('/')
        for page in range(1, page_count + 1):
            page_url = f"{base}/{page}.html"
            try:
                logger.info("列表抓取中 第%s页 地址=%s", page, page_url)
                async with session.get(page_url, timeout=10) as response:
                    response.raise_for_status()
                    html = await response.text(encoding='utf-8', errors='ignore')
                
                # 解析HTML
                soup = BeautifulSoup(html, 'html.parser')
                
                # 根据HTML结构，新闻项在class为"item"的div中
                items = soup.find_all('div', class_='item')
                page_items_count = 0
                
                for item in items:
                    try:
                        news_info = self._parse_news_item(item)#对每个item进行解析
                        if news_info:
                            news_list.append(news_info)
                            page_items_count += 1
                    except Exception as e:
                        logger.warning("解析新闻项时出错: %s", e)
                        continue
                
                logger.info("列表页完成 第%s页 条数=%s", page, page_items_count)
                await asyncio.sleep(0.2)  # 控制抓取节奏
            
            except aiohttp.ClientError as e:
                logger.warning("列表页网络失败 第%s页 错误=%s", page, e)
            except Exception as e:
                logger.exception("列表页解析失败 第%s页 错误=%s", page, e)
        
        logger.info("列表抓取完成 页数=%s 总数=%s", page_count, len(news_list))
        return news_list
    
    def _parse_news_item(self, item) -> Dict:
        """
        解析单个新闻项
        
        Args:
            item: BeautifulSoup对象，包含单个新闻项的HTML
            
        Returns:
            Dict: 包含新闻信息的字典
        """
        news_info = {}
        
        # 提取标题
        title_link = item.find('h2').find('a') if item.find('h2') else None
        if title_link:
            news_info['title'] = title_link.get_text(strip=True)
            # 提取详细URL
            news_info['detail_url'] = title_link.get('href', '').strip()
        else:
            return None
        
        # 提取简介
        description = item.find('p', class_='text-justify')
        if description:
            news_info['description'] = description.get_text(strip=True)
        else:
            news_info['description'] = ""
        
        # 添加爬虫标识
        news_info['crawler'] = 'bioon'
        
        return news_info
    
    async def fetch_news_detail(self, session: aiohttp.ClientSession, news_item: Dict) -> Dict:
        """
        抓取单个新闻详情页面的完整内容
        
        Args:
            news_item: 包含detail_url的新闻项字典
            
        Returns:
            Dict: 更新后的新闻项，包含详情页面的完整内容
        """
        if not news_item.get('detail_url'):
            logger.warning("新闻项缺少detail_url，跳过: %s", news_item.get('title', '未知标题'))
            return news_item
        
        detail_url = news_item['detail_url']
        
        try:
            logger.debug("详情抓取中 地址=%s", detail_url)
            async with session.get(detail_url, timeout=10) as response:
                response.raise_for_status()
                html = await response.text(encoding='utf-8', errors='ignore')
            
            # 解析详情页HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # 提取来源与日期，例如：
            # <p class="source_text">来源：生物世界 2025-11-17 16:09</p>
            source_p = soup.find('p', class_='source_text')
            if source_p:
                source_text = source_p.get_text(strip=True)

                # 标准化冒号为半角
                source_text = source_text.replace('：', ':')

                # 正则匹配：来源名 + 日期 + 时间
                # 例如：来源:iNature 2025-12-01 14:43
                pattern = r'^来源:(?P<source>.*?)\s+(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2})$'
                m = re.match(pattern, source_text)

                if m:
                    news_item['source'] = m.group('source').strip()
                    news_item['publish_time'] = f"{m.group('date')} {m.group('time')}"
                else:
                    # 兜底：至少填一下
                    news_item['source'] = source_text
                    news_item.setdefault('publish_time', '')
            else:
                news_item.setdefault('source', '')
                news_item.setdefault('publish_time', '')
            
            content_elem = soup.find('div', attrs={'style': 'color: #303a4e;'})
            if content_elem:
                #删除center标签
                center_p_tags = content_elem.find_all('p',style=re.compile(r'text-align:\s*center', re.I))# 正则匹配：style 包含 text-align: center（忽略空格和大小写）
                # 逐个删除这些标签
                for p_tag in center_p_tags:
                    p_tag.decompose()  # 从文档树中移除该标签，后续提取文本时不再包含
                # 提取完整文本内容
                full_text = content_elem.get_text(separator='\n', strip=True)
                full_text = re.sub(r'(?<![。！？；：.!?;:( )）])\n','',full_text)  # 正则模式：前面不是标点的\n，替换为空（去掉该换行）
                news_item['full_text'] = full_text
                
            else:
                news_item['full_text'] = ""
                logger.warning("未找到详情页内容区域: %s", detail_url)
            
            import random
            base_delay=0.3
            random_delay=random.uniform(0.1,0.3)
            await asyncio.sleep(base_delay+random_delay)  # 避免单站压力过大
            
        except aiohttp.ClientError as e:
            logger.warning("抓取详情页失败: %s, 错误: %s", detail_url, str(e))
            news_item['full_text'] = ""
        except Exception as e:
            logger.exception("解析详情页失败: %s, 错误: %s", detail_url, str(e))
            news_item['full_text'] = ""
        
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
        async def _fetch(item: Dict):
            await self.fetch_news_detail(session, item)

        return await self.run_fetch_details(
            news_list=news_list,
            fetch_detail_func=_fetch,
            concurrency=concurrency,
            crawler_label=crawler_name,
            logger_name="bioon",
        )
    
    def save_to_json(self, news_list: List[Dict], filename: str =f"outjson/{crawler_name}.json"):
        """
        将新闻数据保存为JSON文件
        
        Args:
            news_list: 新闻数据列表
            filename: 保存的文件名
        """
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(news_list, f, ensure_ascii=False, indent=2)
            logger.info("新闻数据已保存到: %s", filename)
        except Exception as e:
            logger.exception("保存文件失败: %s", e)
    
    def print_news_list(self, news_list: List[Dict]):
        """
        打印新闻列表
        
        Args:
            news_list: 新闻数据列表
        """
        logger.info("%s", "=" * 80)
        logger.info("Bioon新闻采集结果")
        logger.info("%s", "=" * 80)
        
        for i, news in enumerate(news_list, 1):
            logger.info("%s. 标题: %s", i, news.get('title', ''))
            logger.info("   日期: %s", news.get('publish_time', ''))
            logger.info(
                "   简介: %s",
                f"{news.get('description', '')[:100]}..." if len(news.get('description', '')) > 100 else news.get('description', ''),
            )
            logger.info(
                "   正文: %s",
                f"{news.get('full_text', '')[:100]}..." if len(news.get('full_text', '')) > 100 else news.get('full_text', ''),
            )
            logger.info("   详细URL: %s", news.get('detail_url', ''))
            logger.info("   %s", "-" * 70)
        
        logger.info("总计采集到 %s 条新闻", len(news_list))
    


async def crawl_bioon_news_async(
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
    crawler = BioonNewsCrawler(user_agent=user_agent)
    start_time = time.perf_counter()
    logger.info(
        "采集开始 页数=%s 抓取详情=%s 并发=%s",
        page_count,
        fetch_details,
        concurrency,
    )
    visited_urls = set()
    visited_file=f"outjson/{crawler_name}_url.json"
    visited_urls = crawler.load_visited_urls(visited_file)
    
    async with aiohttp.ClientSession(headers=crawler.headers) as session:
        raw_news_list: List[Dict] = await crawler.fetch_news_list(session, page_count=page_count)
        new_news_list = crawler.filter_new_items(raw_news_list, visited_urls)
        logger.info(
            "增量过滤完成 原始=%s 过滤=%s 新增=%s",
            len(raw_news_list),
            len(raw_news_list) - len(new_news_list),
            len(new_news_list),
        )

        if not raw_news_list:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info("采集完成 总数=0 耗时=%s毫秒", elapsed_ms)
            return []

        if not new_news_list:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info("采集完成 总数=0 耗时=%s毫秒", elapsed_ms)
            return []

        if fetch_details:
            news_list = await crawler.fetch_all_details(session, new_news_list, concurrency=concurrency)
            crawler.save_visited_urls_union(visited_file, visited_urls, raw_news_list)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info("采集完成 总数=%s 耗时=%s毫秒", len(news_list), elapsed_ms)
            return news_list

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info("采集完成 总数=%s 耗时=%s毫秒", len(new_news_list), elapsed_ms)
        return new_news_list
        


if __name__ == "__main__":
    # 示例：抓取前 3 页列表 + 详情页，详情并发数 10
    asyncio.run(crawl_bioon_news_async(page_count=1, fetch_details=True, concurrency=3))