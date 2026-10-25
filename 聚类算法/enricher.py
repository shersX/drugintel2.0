# -*- coding: utf-8 -*-
"""
LLM 增强：生成摘要 + 抽取归一化实体（药物/企业/事件类型）
兼容任何 OpenAI 兼容接口，包括本地 Ollama（base_url=http://localhost:11434/v1）
或本地 Qwen GGUF 启动的 OpenAI 兼容服务。
"""
import json
import re

SYSTEM_PROMPT = (
    "你是医药竞争情报分析助手。阅读新闻，输出严格的 JSON，字段如下：\n"
    '{"summary": "1-2句中文摘要，保留药物名、企业名、关键事件",\n'
    ' "drugs": ["药物/疗法的标准英文名，同义词归一化，无则空数组"],\n'
    ' "orgs": ["企业/机构标准英文名，同一公司的不同写法归一化"],\n'
    ' "event_type": "clinical 或 approval 或 m&a 或 safety 或 other"}\n'
    "只输出 JSON，不要解释。"
)


class Enricher:
    def __init__(self, base_url: str = "http://localhost:11434/v1",
                 api_key: str = "ollama", model: str = "qwen2.5:7b"):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def enrich(self, title: str, content: str) -> dict:
        user = f"标题：{title}\n正文：{content[:4000]}"
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> dict:
        raw = raw.strip()
        # 兼容模型偶尔输出 ```json 包裹
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0) if m else raw)
        return {
            "summary": data.get("summary", ""),
            "drugs": [str(x).strip().lower() for x in data.get("drugs", []) if x],
            "orgs": [str(x).strip().lower() for x in data.get("orgs", []) if x],
            "event_type": str(data.get("event_type", "other")).strip().lower(),
        }
#（注：内容由AI生成）
