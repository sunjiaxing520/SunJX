"""Build the five-page reading copy from the handbook Markdown (ReportLab)."""
from pathlib import Path
import re
from html import escape

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle, Preformatted, Spacer
from reportlab.pdfgen import canvas
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '大数据运维面试速查手册.md'
OUTPUT = ROOT / '大数据运维面试速查手册-5页.pdf'
pdfmetrics.registerFont(TTFont('YaHei', 'C:/Windows/Fonts/msyh.ttc'))
pdfmetrics.registerFont(TTFont('YaHeiBold', 'C:/Windows/Fonts/msyhbd.ttc'))
pdfmetrics.registerFontFamily('YaHei', normal='YaHei', bold='YaHeiBold', italic='YaHei', boldItalic='YaHeiBold')
WIDTH, HEIGHT = A4
MARGIN = 34
CONTENT_WIDTH = WIDTH - MARGIN * 2
CONTENT_HEIGHT = HEIGHT - 82
INK = colors.HexColor('#162D41')
ACCENT = colors.HexColor('#126B78')


def clean(value):
    return value.replace('🔥', '[必考]').replace('⭐', '[重点]').replace('—', '-').replace('–', '-')


def inline(value):
    value = escape(clean(value.replace(r'\|', '|')))
    value = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<link href="\2" color="#126B78">\1</link>', value)
    value = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', value)
    value = re.sub(r'`([^`]+)`', r'<font color="#126B78">\1</font>', value)
    return value


def make_page(text, size):
    body = ParagraphStyle('body', fontName='YaHei', fontSize=size, leading=size * 1.45,
                          textColor=INK, wordWrap='CJK', spaceAfter=5, alignment=TA_LEFT)
    heading = ParagraphStyle('heading', parent=body, fontName='YaHeiBold', fontSize=size + 4,
                             leading=(size + 4) * 1.35, spaceBefore=5, spaceAfter=9)
    title = ParagraphStyle('title', parent=heading, fontSize=size + 9, leading=(size + 9) * 1.3)
    cell = ParagraphStyle('cell', parent=body, fontSize=size, leading=size * 1.36, spaceAfter=0)
    code = ParagraphStyle('code', parent=body, fontSize=size - 0.1, leading=size * 1.38,
                          backColor=colors.HexColor('#EDF4F6'), borderPadding=5, spaceAfter=8)
    source = ParagraphStyle('source', parent=body, fontSize=size - 0.8, leading=size * 1.2,
                            textColor=colors.HexColor('#526878'))
    lines = text.strip().splitlines()
    items = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith('```'):
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                block.append(clean(lines[i]))
                i += 1
            items.append(Preformatted('\n'.join(block), code))
        elif line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                parts = re.split(r'(?<!\\)\|', lines[i].strip()[1:-1])
                if not all(re.fullmatch(r'\s*:?-+:?\s*', item) for item in parts):
                    rows.append([Paragraph(inline(item.strip()), cell) for item in parts])
                i += 1
            count = len(rows[0])
            fractions = [0.19, 0.35, 0.46] if count == 3 else [0.48, 0.52]
            if count == 2 and rows and '治理' in text and len(rows) == 3:
                fractions = [0.19, 0.81]
            table = Table(rows, colWidths=[CONTENT_WIDTH * f for f in fractions], hAlign='LEFT')
            table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D9E9ED')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F6F8')]),
                ('LINEBELOW', (0, 0), (-1, 0), 0.6, ACCENT),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            items.extend([table, Spacer(1, 7)])
            continue
        elif line.startswith('## '):
            items.append(Paragraph(inline(line[3:]), heading))
        elif line.startswith('# '):
            items.append(Paragraph(inline(line[2:]), title))
        else:
            items.append(Paragraph(inline(line), source if line.startswith('来源：') else body))
        i += 1
    return items


def measured(items):
    return sum(item.wrap(CONTENT_WIDTH, CONTENT_HEIGHT)[1] + item.getSpaceBefore() + item.getSpaceAfter()
               for item in items)


def main():
    sections = SOURCE.read_text(encoding='utf-8').split('<!-- PAGEBREAK -->')
    assert len(sections) == 5, 'Expected exactly five source sections'
    chosen = None
    for size in [10.0, 9.8, 9.6, 9.4, 9.2, 9.0, 8.8]:
        pages = [make_page(section, size) for section in sections]
        heights = [measured(page) for page in pages]
        if max(heights) <= CONTENT_HEIGHT:
            chosen = size, pages, heights
            break
    if chosen is None:
        raise ValueError('Content exceeds five readable pages; edit source rather than clipping it')
    size, pages, heights = chosen
    pdf = canvas.Canvas(str(OUTPUT), pagesize=A4)
    pdf.setTitle('大数据运维面试速查手册 - 5页')
    pdf.setAuthor('面试突击学习项目')
    for number, items in enumerate(pages, 1):
        pdf.setFillColor(ACCENT)
        pdf.rect(MARGIN, HEIGHT - 19, 35, 3, fill=1, stroke=0)
        y = HEIGHT - 36
        for item in items:
            width, height = item.wrap(CONTENT_WIDTH, CONTENT_HEIGHT)
            y -= item.getSpaceBefore()
            y -= height
            assert y >= 40, (number, y)
            item.drawOn(pdf, MARGIN, y)
            y -= item.getSpaceAfter()
        pdf.setFont('YaHei', 8)
        pdf.setFillColor(colors.HexColor('#526878'))
        pdf.drawString(MARGIN, 22, '面试突击 / 2026.09.27 / 版本基线见第1页')
        pdf.drawRightString(WIDTH - MARGIN, 22, f'{number} / 5')
        pdf.showPage()
    pdf.save()
    reader = PdfReader(OUTPUT)
    assert len(reader.pages) == 5
    for number, page in enumerate(reader.pages, 1):
        assert f'第 {number} 页' in page.extract_text(), number
    print(f'Created {OUTPUT.name}: 5 pages, font={size}pt; heights={list(map(lambda h: round(h, 1), heights))}')


if __name__ == '__main__':
    main()
