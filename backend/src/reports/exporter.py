"""研究报告导出（PDF / Word）。"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Sequence

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from backend.src.core.logger import get_logger
from backend.src.llm.client import SiliconFlowClient

logger = get_logger("reports")

EXPORT_DIR = Path(__file__).resolve().parents[3] / "outjson" / "reports"


async def generate_report_summary(
    question: str,
    answer: str,
    sources: Sequence[Dict[str, Any]],
) -> str:
    llm = SiliconFlowClient.from_env()
    src = "\n".join(
        f"- {s.get('title')}" for s in sources[:8]
    )
    prompt = (
        f"请将以下问答整理为研究报告摘要（300字以内，中文）：\n"
        f"问题：{question}\n回答：{answer}\n来源：\n{src}"
    )
    try:
        return await llm.chat_completion(
            [
                {"role": "system", "content": "你是医药情报报告撰写助手。"},
                {"role": "user", "content": prompt},
            ]
        )
    except Exception as e:
        logger.warning("报告摘要生成失败: %s", e)
        return answer[:300]


def _safe_text(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_pdf_bytes(
    *,
    title: str,
    summary: str,
    question: str,
    answer: str,
    sources: Sequence[Dict[str, Any]],
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(_safe_text(title), styles["Title"]),
        Spacer(1, 0.4 * cm),
        Paragraph(_safe_text(f"生成时间：{datetime.now().isoformat(timespec='seconds')}"), styles["Normal"]),
        Spacer(1, 0.4 * cm),
        Paragraph("<b>摘要</b>", styles["Heading2"]),
        Paragraph(_safe_text(summary), styles["BodyText"]),
        Spacer(1, 0.3 * cm),
        Paragraph("<b>问题</b>", styles["Heading2"]),
        Paragraph(_safe_text(question), styles["BodyText"]),
        Spacer(1, 0.3 * cm),
        Paragraph("<b>回答</b>", styles["Heading2"]),
        Paragraph(_safe_text(answer), styles["BodyText"]),
        Spacer(1, 0.3 * cm),
        Paragraph("<b>来源</b>", styles["Heading2"]),
    ]
    for i, s in enumerate(sources, start=1):
        story.append(
            Paragraph(
                _safe_text(f"[{i}] {s.get('title') or ''} {s.get('detail_url') or ''}"),
                styles["Normal"],
            )
        )
    doc.build(story)
    return buf.getvalue()


def build_docx_bytes(
    *,
    title: str,
    summary: str,
    question: str,
    answer: str,
    sources: Sequence[Dict[str, Any]],
) -> bytes:
    document = Document()
    document.add_heading(title, level=1)
    document.add_paragraph(f"生成时间：{datetime.now().isoformat(timespec='seconds')}")
    document.add_heading("摘要", level=2)
    document.add_paragraph(summary)
    document.add_heading("问题", level=2)
    document.add_paragraph(question)
    document.add_heading("回答", level=2)
    document.add_paragraph(answer)
    document.add_heading("来源", level=2)
    for i, s in enumerate(sources, start=1):
        document.add_paragraph(
            f"[{i}] {s.get('title') or ''} {s.get('detail_url') or ''}",
            style="List Number",
        )
    buf = BytesIO()
    document.save(buf)
    return buf.getvalue()


async def export_report(
    *,
    question: str,
    answer: str,
    sources: Sequence[Dict[str, Any]],
    fmt: str = "pdf",
) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = await generate_report_summary(question, answer, sources)
    title = "DrugIntel 研究报告"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "docx":
        data = build_docx_bytes(
            title=title, summary=summary, question=question, answer=answer, sources=sources
        )
        path = EXPORT_DIR / f"report_{stamp}.docx"
    else:
        data = build_pdf_bytes(
            title=title, summary=summary, question=question, answer=answer, sources=sources
        )
        path = EXPORT_DIR / f"report_{stamp}.pdf"
    path.write_bytes(data)
    return path
