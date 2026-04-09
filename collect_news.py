"""
Step 1: RSS フィードから最新 AI ニュースを収集する
"""
import re
from datetime import datetime

import feedparser

RSS_FEEDS = [
    ("TechCrunch Japan",  "https://jp.techcrunch.com/feed/"),
    ("ITmedia AI+",       "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml"),
    ("ASCII.jp",          "https://ascii.jp/rss.xml"),
    ("Gigazine",          "https://gigazine.net/news/rss_2.0/"),
    ("CNET Japan",        "https://japan.cnet.com/news/rss.htm"),
    ("XenoSpectrum",      "https://xenospectrum.com/feed/"),
]

_TAG_RE = re.compile(r"<[^>]+>")

AI_KEYWORDS = [
    "AI", "人工知能", "機械学習", "ディープラーニング", "深層学習",
    "生成AI", "大規模言語モデル", "LLM", "GPT", "Claude", "Gemini",
    "ChatGPT", "Copilot", "自動化", "自律", "チャットボット",
    "画像生成", "音声認識", "自然言語", "データサイエンス",
    "OpenAI", "Anthropic", "Google DeepMind", "Meta AI", "Microsoft AI",
]


def _is_ai_related(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in AI_KEYWORDS)


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


def _parse_date(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6])
            except Exception:
                pass
    return datetime.now()


def collect_news(top_n: int = 10) -> list[dict]:
    all_items: list[dict] = []

    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                summary = _strip_html(getattr(entry, "summary", ""))[:300]
                if not _is_ai_related(entry.title, summary):
                    continue
                all_items.append(
                    {
                        "title":     entry.title,
                        "summary":   summary,
                        "url":       entry.link,
                        "published": _parse_date(entry),
                        "source":    source_name,
                    }
                )
        except Exception as exc:
            print(f"  [警告] {source_name} の取得に失敗: {exc}")

    # 新しい順にソート
    all_items.sort(key=lambda x: x["published"], reverse=True)

    # タイトルの先頭50文字で重複排除
    seen: set[str] = set()
    unique: list[dict] = []
    for item in all_items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique[:top_n]


if __name__ == "__main__":
    news = collect_news()
    for i, item in enumerate(news, 1):
        print(f"{i:2}. [{item['source']}] {item['title']}")
        print(f"     {item['published'].strftime('%Y-%m-%d %H:%M')}  {item['url']}")
