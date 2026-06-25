"""
每日简报 - AI 摘要模块
使用 DeepSeek API 进行高质量新闻摘要 + 中英双语翻译
"""
import json
import logging
import re
from datetime import datetime

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    SUMMARY_MAX_TOKENS, CATEGORIES, LANGUAGES,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior news editor at a global briefing desk. Your task is to analyze headlines and produce a high-quality briefing.

**Step 1 — Filter:** Discard advertisements, sponsored content, celebrity gossip, sports scores, and trivial local news. Only keep stories of national/global significance.

**Step 2 — Select:** Choose the 3-5 most important stories per category. Prioritize:
- Events that affect international relations, markets, or security
- Policy changes, elections, diplomatic developments
- Major military conflicts, defense deals, security threats
- Breakthrough technologies, major tech policy, cybersecurity events

**Step 3 — Write:** For each selected story, write:
- `title_en`: A clear, factual English headline (keep original if it's good, rewrite if clickbait)
- `summary_en`: 2-4 sentences in English explaining WHAT happened and WHY it matters
- `title_zh`: Natural Chinese translation of the title (地道的中文翻译)
- `summary_zh`: Natural Chinese translation of the summary (地道的中文翻译)
- `importance`: 1-5 rating (5 = major global impact)

**Output MUST be valid JSON only:**
```json
{
  "political": [
    {"title_en": "...", "summary_en": "...", "title_zh": "...", "summary_zh": "...", "importance": 5}
  ],
  "economic": [...],
  "military": [...],
  "technology": [...]
}
```

If a category has no important news, return an empty array `[]` for it."""


def _call_deepseek(system_prompt: str, user_message: str) -> dict:
    """调用 DeepSeek API，强制 JSON 输出"""
    from openai import OpenAI

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    logger.info(f"调用 DeepSeek API ({DEEPSEEK_MODEL})...")
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=SUMMARY_MAX_TOKENS,
        temperature=0.3,
        response_format={"type": "json_object"},  # 强制 JSON 模式
    )

    raw = response.choices[0].message.content.strip()
    logger.info(f"DeepSeek 返回 {len(raw)} 字符")

    # 去除 markdown 代码块包裹
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)
    raw = raw.strip()

    # 尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 解析失败: {e}，尝试修复...")
        # 保存原始响应用于调试
        debug_path = BASE_DIR / "audio" / "_last_response.txt"
        debug_path.write_text(raw, encoding="utf-8")
        logger.info(f"原始响应已保存至 {debug_path}")

    # 尝试提取最外层 {...}
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    # 尝试修复常见 JSON 错误
    fixed = _repair_json(raw)
    if fixed:
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法解析 DeepSeek 返回的 JSON，已保存原始响应")


def _repair_json(text: str) -> str | None:
    """尝试修复常见的 JSON 格式错误"""
    # 1. 提取 outermost brace block
    depth = 0
    start = text.find("{")
    if start == -1:
        return None
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                text = text[start:i + 1]
                break
    else:
        return None  # 未闭合

    # 2. 移除尾部多余字符
    text = text.strip()

    # 3. 修复字符串中未转义的控制字符
    # (DeepSeek 有时在 JSON 字符串中包含未转义的换行符)
    fixed = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            fixed.append(ch)
            escape = False
            continue
        if ch == "\\" and in_string:
            fixed.append(ch)
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            fixed.append(ch)
            continue
        if in_string and ch in "\n\r\t":
            fixed.append(" " if ch in "\n\r" else "\\t")
            continue
        fixed.append(ch)

    return "".join(fixed)


def summarize(news_text: str, language: str = "chinese") -> dict:
    """
    调用 AI 对新闻进行摘要。

    返回格式:
    {
      "political": [
        {"title_en": "...", "summary_en": "...", "title_zh": "...", "summary_zh": "...", "importance": 5}
      ], ...
    }
    """
    if not DEEPSEEK_API_KEY:
        logger.warning("未配置 DEEPSEEK_API_KEY，使用本地模式")
        return _fallback_summary(news_text, language)

    try:
        lang_name = LANGUAGES.get(language, LANGUAGES["chinese"])["name"]
        user_message = f"""Here are headlines from the past 24 hours:

{news_text}

Please produce the briefing now. All titles and summaries must be bilingual (English + Chinese)."""

        result = _call_deepseek(SYSTEM_PROMPT, user_message)

        # 确保所有分类都存在
        for cat in CATEGORIES:
            if cat not in result:
                result[cat] = []

        total = sum(len(v) for v in result.values())
        logger.info(f"AI 摘要完成: {total} 条重要新闻")
        return result

    except Exception as e:
        logger.error(f"AI 摘要失败: {e}")
        return _fallback_summary(news_text, language)


def _fallback_summary(news_text: str, language: str) -> dict:
    """本地备用摘要（无 API 时使用）"""
    result = {}
    current_cat = None
    titles: list[str] = []

    for line in news_text.split("\n"):
        for cat_key, cat_info in CATEGORIES.items():
            if cat_info["name_en"] in line or cat_info["name_zh"] in line:
                if current_cat and titles:
                    result[current_cat] = [
                        {
                            "title_en": t, "summary_en": t,
                            "title_zh": t, "summary_zh": "",
                            "importance": 3,
                        }
                        for t in titles[:5]
                    ]
                current_cat = cat_key
                titles = []
                break
        else:
            m = re.match(r"^\d+\.\s+(.+)", line)
            if m and current_cat:
                titles.append(m.group(1).strip())

    if current_cat and titles:
        result[current_cat] = [
            {
                "title_en": t, "summary_en": t,
                "title_zh": t, "summary_zh": "",
                "importance": 3,
            }
            for t in titles[:5]
        ]

    for cat in CATEGORIES:
        if cat not in result:
            result[cat] = []

    logger.info("使用本地备用摘要模式")
    return result


def build_briefing_text(summary: dict, language: str = "chinese") -> tuple[str, str]:
    """
    将摘要构建为可读文本和 HTML。

    返回: (plain_text, html_text)
    """
    is_en = language == "english"

    if language == "chinese":
        labels = {"political": "政治", "economic": "经济", "military": "军事", "technology": "科技"}
        date_label = "每日简报"
        greeting = "早上好！以下是过去 24 小时的全球要闻简报。"
    elif language == "cantonese":
        labels = {"political": "政治", "economic": "經濟", "military": "軍事", "technology": "科技"}
        date_label = "每日簡報"
        greeting = "早晨！以下係過去 24 小時嘅全球要聞簡報。"
    else:
        labels = {"political": "Politics", "economic": "Economy", "military": "Military", "technology": "Technology"}
        date_label = "Daily Briefing"
        greeting = "Good morning! Here is your briefing of global events from the past 24 hours."

    today = datetime.now().strftime("%Y-%m-%d")

    # ── 纯文本（用于 TTS）──
    plain_lines = [f"═══ {date_label} · {today} ═══", "", greeting, ""]
    for cat_key in ["political", "economic", "military", "technology"]:
        items = summary.get(cat_key, [])
        if not items:
            continue
        plain_lines.append(f"▸ {labels[cat_key]}")
        plain_lines.append("─" * 40)
        for i, item in enumerate(items[:5], 1):
            stars = "★" * item.get("importance", 3)
            if is_en:
                plain_lines.append(f"  {i}. {item.get('title_en', item.get('title', ''))}  {stars}")
                s = item.get("summary_en", item.get("summary", ""))
            else:
                title = item.get("title_zh") or item.get("title_en") or item.get("title", "")
                plain_lines.append(f"  {i}. {title}  {stars}")
                s = item.get("summary_zh") or item.get("summary_en") or item.get("summary", "")
            if s and s != item.get("title_en", ""):
                plain_lines.append(f"     {s}")
        plain_lines.append("")
    plain_text = "\n".join(plain_lines)

    # ── HTML ──
    html_parts = [
        '<div class="briefing-container">',
        f'<div class="briefing-header">',
        f'<h1>{date_label}</h1>',
        f'<div class="briefing-date">{today}</div>',
        f'<p class="briefing-greeting">{greeting}</p>',
        f'</div>',
    ]

    for cat_key in ["political", "economic", "military", "technology"]:
        cat_info = CATEGORIES[cat_key]
        items = summary.get(cat_key, [])
        html_parts.append(
            f'<div class="category-card" style="border-left: 4px solid {cat_info["color"]}">'
        )
        html_parts.append(
            f'<h2 class="category-title">{cat_info["icon"]} {labels[cat_key]}</h2>'
        )
        if not items:
            html_parts.append('<p class="no-news">暂无重要新闻 / No major news</p>')
        else:
            html_parts.append('<ol class="news-list">')
            for item in items[:5]:
                stars = "★" * item.get("importance", 3) + "☆" * (5 - item.get("importance", 3))

                if is_en:
                    title_main = item.get("title_en") or item.get("title", "")
                    summary_main = item.get("summary_en") or item.get("summary", "")
                    title_sub = item.get("title_zh", "")
                    summary_sub = item.get("summary_zh", "")
                else:
                    title_main = item.get("title_zh") or item.get("title_en") or item.get("title", "")
                    summary_main = item.get("summary_zh") or item.get("summary_en") or item.get("summary", "")
                    title_sub = item.get("title_en", "")
                    summary_sub = item.get("summary_en", "")

                html_parts.append(
                    f'<li class="news-item">'
                    f'<div class="news-title">{_escape(title_main)}</div>'
                    f'<div class="news-summary">{_escape(summary_main)}</div>'
                )
                # 双语：显示原文对照
                if title_sub and title_sub != title_main:
                    html_parts.append(
                        f'<div class="news-original">🌐 {_escape(title_sub)}</div>'
                    )
                html_parts.append(
                    f'<div class="news-importance" style="color:{cat_info["color"]}">{stars}</div>'
                    f'</li>'
                )
            html_parts.append('</ol>')
        html_parts.append('</div>')

    html_parts.append('</div>')
    html_text = "\n".join(html_parts)

    return plain_text, html_text


def _escape(s: str) -> str:
    """HTML 转义"""
    if not s:
        return ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
