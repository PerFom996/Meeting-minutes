# -*- coding: utf-8 -*-
"""生成「会议纪要 App」使用手册 .docx"""
import os, sys
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(OUT_DIR, "会议纪要App使用手册.docx")

doc = Document()

# ── 全局默认字体 ──
style = doc.styles["Normal"]
style.font.name = "Microsoft YaHei"
style.font.size = Pt(11)
style.paragraph_format.space_after = Pt(6)
style.paragraph_format.line_spacing = 1.35
# 东亚字体
style.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")

# 默认标题样式
for level in range(1, 4):
    hs = doc.styles[f"Heading {level}"]
    hs.font.name = "Microsoft YaHei"
    hs.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    hs.font.color.rgb = RGBColor(0x1A, 0x21, 0x30)

def add_para(text, bold=False, size=None, color=None, align=None):
    p = doc.add_paragraph()
    run = p.add_run(text)
    if bold:
        run.bold = True
    if size:
        run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor(*color)
    if align is not None:
        p.alignment = align
    return p

def add_bullet(text, level=0):
    p = doc.add_paragraph(text, style="List Bullet")
    if level:
        p.paragraph_format.left_indent = Cm(1.2 * level)
    return p

def add_table(headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
                run.font.size = Pt(10)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = table.rows[ri + 1].cells[ci]
            cell.text = val
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(10)
    doc.add_paragraph()
    return table

# ══════════════════════════════════════════
# 封面
# ══════════════════════════════════════════
doc.add_paragraph()
doc.add_paragraph()
add_para("会议纪要 App", bold=True, size=28, color=(0x16, 0x5D, 0xFF), align=WD_ALIGN_PARAGRAPH.CENTER)
add_para("使用手册  v2.0", bold=True, size=16, color=(0x5B, 0x66, 0x7A), align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
add_para("说话即记录，散会即纪要", size=13, color=(0x98, 0xA1, 0xB3), align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
doc.add_paragraph()
add_para("2026年10月", size=11, color=(0x98, 0xA1, 0xB3), align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_page_break()

# ══════════════════════════════════════════
# 目录概览
# ══════════════════════════════════════════
doc.add_heading("目录", level=1)
toc = [
    "1. 产品简介",
    "2. 快速上手（3 分钟）",
    "3. 界面说明",
    "4. 两种录音模式",
    "5. 文字纠错",
    "6. 生成会议纪要",
    "7. 结果导出与复制",
    "8. 历史记录",
    "9. 设置与会人",
    "10. .env 配置指南（进阶）",
    "11. 快捷键",
    "12. 常见问题",
]
for t in toc:
    add_para(t)
doc.add_page_break()

# ══════════════════════════════════════════
# 1
# ══════════════════════════════════════════
doc.add_heading("1. 产品简介", level=1)
add_para("「会议纪要 App」是一款桌面端会议记录与总结工具。您可以在开会时说话，它会自动将语音转成文字，并在散会后一键生成结构化的会议纪要，包含议题要点、已定事项、待办清单、风险提示和关键词。")
add_para("核心特点：", bold=True)
add_bullet("双模式录音：浏览器实时识别（边说话边出字） + 服务端语音转写（录音后上传转写）。")
add_bullet("文字纠错：一键调用 AI 纠正同音错字、补全标点、去除口语碎片。")
add_bullet("双引擎纪要：有 AI 时走大模型深度总结；未配置时自动降级为本地规则引擎，数据不出本机。")
add_bullet("离线可用：不配置任何 API Key 依然可以使用浏览器实时语音识别 + 本地摘要。")
add_bullet("历史回顾：自动保存最近 20 次会议记录，随时回看。")
add_bullet("导出方便：支持复制 Markdown 和导出 .md 文件。")
doc.add_paragraph()

# ══════════════════════════════════════════
# 2
# ══════════════════════════════════════════
doc.add_heading("2. 快速上手（3 分钟）", level=1)
add_para("Step 1 — 启动程序", bold=True)
add_bullet("双击「启动会议纪要.bat」，会弹出一个独立窗口。")
add_bullet("如果提示缺少 Python，请先安装 Python 3.10+ 并执行 pip install -r requirements.txt。")
doc.add_paragraph()
add_para("Step 2 — 开始记录", bold=True)
add_bullet("点击蓝色「开始记录」按钮，允许浏览器使用麦克风。")
add_bullet("开始说话，左侧「实时字幕」和下方文本框会同步出现文字。")
doc.add_paragraph()
add_para("Step 3 — 生成纪要", bold=True)
add_bullet("点击「生成纪要」按钮，右侧将显示结构化的会议纪要。")
add_bullet("也可以点击「文字纠错」先用 AI 优化识别文字，再生成纪要效果更好。")
doc.add_paragraph()
add_para("Step 4 — 导出", bold=True)
add_bullet("点击「复制」可复制 Markdown 格式全文。")
add_bullet("点击「导出 Markdown」可将纪要保存为 .md 文件到本地。")
doc.add_page_break()

# ══════════════════════════════════════════
# 3
# ══════════════════════════════════════════
doc.add_heading("3. 界面说明", level=1)
add_table(
    ["区域", "位置", "功能"],
    [
        ["顶栏", "窗口最上", "显示当前状态（待命/识别中/生成中/完成），以及「历史」「设置」入口。"],
        ["会议内容区", "左侧面板", "录音按钮、计时器、实时字幕、文字编辑框、字数统计。"],
        ["模式切换", "左侧面板右上", "在「实时识别」和「录音转写」之间切换。"],
        ["纠错按钮", "左侧面板左下", "对文本框里的文字进行 AI 纠错或本地规范化。"],
        ["会议纪要区", "右侧面板", "生成结果展示区域，包含议题、决议、待办、风险、关键词。"],
        ["引擎切换", "右侧面板右上", "「智能」= 优先用大模型；「本地」= 只用本地规则引擎。"],
        ["导出按钮", "右侧面板右下", "复制 Markdown 或导出 .md 文件。"],
    ],
)
doc.add_paragraph()

# ══════════════════════════════════════════
# 4
# ══════════════════════════════════════════
doc.add_heading("4. 两种录音模式", level=1)

doc.add_heading("4.1 实时识别", level=2)
add_para("使用浏览器内置的语音识别引擎，边说边出文字，延迟通常在 1-3 秒以内。", bold=False)
add_bullet("优点：零配置、实时出字、数据不出本机电脑。")
add_bullet("缺点：依赖 Chrome/Edge 浏览器内核，识别精度一般，受网络质量影响。")
add_bullet("适用场景：快速记录、不需要极高精度的日常讨论。")
doc.add_paragraph()

doc.add_heading("4.2 录音转写", level=2)
add_para("需要先在 .env 中配置 ASR_API_KEY（如硅基流动的 SenseVoice 模型）。点击「开始记录」后会录制完整音频，停止时自动上传到服务端转写，准确度远高于浏览器引擎。", bold=False)
add_bullet("优点：识别准确率高、支持较长录音。")
add_bullet("缺点：需要额外配置 ASR Key、转写有等待时间。")
add_bullet("适用场景：正式会议、需要高准确率的场景。")
doc.add_page_break()

# ══════════════════════════════════════════
# 5
# ══════════════════════════════════════════
doc.add_heading("5. 文字纠错（v2.0 新增）", level=1)
add_para("语音识别难免产生同音错字（例如「求工程」↔「需求工程」、「属于本体库」↔「术语本体库」）、缺少标点、夹杂口语填充词等问题。")
add_para("点击「✨ 文字纠错」按钮后：", bold=True)
add_bullet("如果已配置 LLM：调用 AI 模型对全文做专业校对，纠正错字、补全标点、去除口语碎片。")
add_bullet("如果未配置 LLM：自动执行本地规范化——英文标点转中文标点、去多余空格和填充词。")
add_bullet("纠错完成后直接在文本框显示结果，您可以手动再调整。")
add_para("💡 建议：生成纪要之前先点一次「文字纠错」，可显著提升纪要质量。", bold=True)
doc.add_paragraph()

# ══════════════════════════════════════════
# 6
# ══════════════════════════════════════════
doc.add_heading("6. 生成会议纪要", level=1)
add_para("点击「生成纪要」后，系统会根据当前文本生成如下结构化内容：", bold=False)
add_table(
    ["字段", "说明"],
    [
        ["会议主题", "自动从内容中推断，最多 12 字；也可在设置中手工填写。"],
        ["概述", "120-200 字的整体结论式摘要（大模型模式）或统计摘要（本地模式）。"],
        ["议题要点", "按讨论主题分组的关键信息。大模型按语义聚合，本地按关键词锚点分组。"],
        ["已定事项", "已明确的决定、结论、敲定的方向。"],
        ["待办", "需要跟进的事项，含负责人和时间点（识别到则自动填写）。"],
        ["风险与待确认", "阻塞、延期、未达成共识的问题或风险项。"],
        ["关键词", "3-8 个核心关键词，以标签形式展示。"],
    ],
)
doc.add_paragraph()

# ══════════════════════════════════════════
# 7
# ══════════════════════════════════════════
doc.add_heading("7. 结果导出与复制", level=1)
add_para("会议纪要生成后，右侧面板底部提供两种导出方式：", bold=False)
add_bullet("「复制」：一键将完整 Markdown 文本复制到剪贴板，可直接粘贴到飞书、钉钉、企业微信、Notion 等支持 Markdown 的平台。")
add_bullet("「导出 Markdown」：将纪要保存为 .md 文件到本地下载文件夹，文件名格式为「会议主题-日期时间.md」。")
doc.add_paragraph()

# ══════════════════════════════════════════
# 8
# ══════════════════════════════════════════
doc.add_heading("8. 历史记录", level=1)
add_para("点击顶栏「历史」按钮，右侧滑出历史记录抽屉。", bold=False)
add_bullet("自动保存最近 20 次会议的完整记录（含原始文本和生成的纪要）。")
add_bullet("点击任意一条历史记录，左侧文本框和右侧纪要会同步恢复到当时状态，可继续编辑或重新生成。")
add_bullet("历史数据存储在浏览器本地存储中，清除浏览器数据会丢失。")
doc.add_page_break()

# ══════════════════════════════════════════
# 9
# ══════════════════════════════════════════
doc.add_heading("9. 设置与会人", level=1)
add_para("点击顶栏「设置」按钮，弹出设置面板：", bold=False)
add_bullet("「会议主题」：手动指定会议主题，留空则由 AI 自动推断。")
add_bullet("「参会人」：手动输入参会人姓名（逗号分隔），会出现在纪要的元信息中。同时这些名字会作为本地引擎识别「负责人」的参考列表，提高待办事项责任人提取的准确率。")
add_bullet("「能力状态」：显示当前环境的三项能力是否可用——浏览器实时识别、服务端语音转写、大模型纪要。")
doc.add_paragraph()

# ══════════════════════════════════════════
# 10
# ══════════════════════════════════════════
doc.add_heading("10. .env 配置指南（进阶）", level=1)
add_para("要启用服务端语音转写或大模型纪要，需要在程序同目录下创建 .env 文件。将 .env.example 复制为 .env 并填写 API Key。", bold=False)
doc.add_paragraph()

doc.add_heading("10.1 配置大模型（LLM）", level=2)
add_para("示例 —— 使用 DeepSeek：", bold=False)
add_para("LLM_BASE_URL=https://api.deepseek.com/v1\nLLM_API_KEY=sk-your-deepseek-key\nLLM_MODEL=deepseek-chat")
add_para("也支持其他 OpenAI 兼容接口，如通义千问、Kimi、智谱 GLM 等，只需替换 LLM_BASE_URL 和 LLM_MODEL。")
doc.add_paragraph()

doc.add_heading("10.2 配置语音转写（ASR）", level=2)
add_para("示例 —— 使用硅基流动 SenseVoice：", bold=False)
add_para("ASR_BASE_URL=https://api.siliconflow.cn/v1\nASR_API_KEY=sk-your-siliconflow-key\nASR_MODEL=FunAudioLLM/SenseVoiceSmall")
add_para("也支持阿里云百炼等兼容 OpenAI /audio/transcriptions 接口的服务。")
doc.add_paragraph()

doc.add_heading("10.3 运行模式总结", level=2)
add_table(
    ["LLM Key", "ASR Key", "可用能力"],
    [
        ["已配置", "已配置", "服务端转写 + AI 纠错 + 大模型纪要（完整模式）"],
        ["已配置", "未配置", "浏览器实时识别 + AI 纠错 + 大模型纪要"],
        ["未配置", "已配置", "服务端转写 + 本地规则摘要"],
        ["未配置", "未配置", "浏览器实时识别 + 本地规则摘要（纯离线）"],
    ],
)
doc.add_page_break()

# ══════════════════════════════════════════
# 11
# ══════════════════════════════════════════
doc.add_heading("11. 快捷键", level=1)
add_table(
    ["快捷键", "功能"],
    [
        ["Ctrl + Enter", "生成会议纪要"],
    ],
)

doc.add_paragraph()

# ══════════════════════════════════════════
# 12
# ══════════════════════════════════════════
doc.add_heading("12. 常见问题", level=1)

doc.add_heading("Q1：双击 bat 文件没反应？", level=2)
add_bullet("确认已安装 Python 3.10 或更高版本。")
add_bullet("打开命令行，cd 到程序目录，执行 pip install -r requirements.txt 安装依赖。")
add_bullet("再执行 python app.py 查看报错信息。")
doc.add_paragraph()

doc.add_heading("Q2：实时识别经常中断或识别错误？", level=2)
add_bullet("请使用 Chrome 或 Edge 浏览器内核（本应用已内置 Chromium WebView）。")
add_bullet("确保麦克风没有被其他程序占用。")
add_bullet("说话时保持清晰、语速适中。")
add_bullet("停止录音后先点击「文字纠错」，再生成纪要。")
add_bullet("如果对精度要求高，请在 .env 中配置 ASR_API_KEY 改用录音转写模式。")
doc.add_paragraph()

doc.add_heading("Q3：生成纪要时报错「大模型调用失败」？", level=2)
add_bullet("检查 .env 中 LLM_API_KEY 是否正确填写。")
add_bullet("检查 LLM_BASE_URL 是否可正常访问（如 DeepSeek API 是否服务正常）。")
add_bullet("降级方案：将引擎切换到「本地」模式，使用本地规则生成摘要（不依赖网络和 API）。")
doc.add_paragraph()

doc.add_heading("Q4：文字纠错没效果？", level=2)
add_bullet("必须配置 LLM_API_KEY 才能使用 AI 纠错；未配置时仅做本地标点规范化。")
add_bullet("原文太短（少于 10 个字）不会触发纠错。")
add_bullet("纠错结果是 AI 推断，如果上下文混乱，纠正效果会打折扣，建议先检查原文是否通顺。")
doc.add_paragraph()

doc.add_heading("Q5：本地规则摘要和 AI 摘要有什么区别？", level=2)
add_table(
    ["对比项", "本地规则摘要", "AI 摘要（大模型）"],
    [
        ["触发条件", "将引擎切换为「本地」，或未配置 LLM Key", "引擎为「智能」且已配置 LLM Key"],
        ["运行位置", "纯浏览器本地，数据不出机", "调用远程大模型 API"],
        ["摘要风格", "统计数据式概述，如「本次记录共 12 句、约 580 字」", "自然语言结论式摘要，120-200 字"],
        ["速度", "秒级返回", "几秒到十几秒"],
        ["准确度", "规则匹配，可能漏判或误判", "AI 理解，语义准确度高"],
        ["是否需要 Key", "不需要", "需要 LLM_API_KEY"],
    ],
)

# ── 保存 ──
doc.save(OUT_PATH)
print(f"手册已生成：{OUT_PATH}")