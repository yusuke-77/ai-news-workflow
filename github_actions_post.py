"""
GitHub Actions 用スタンドアロン実行スクリプト
RSS収集 → AIフィルタリング → Slack #general 投稿
環境変数: SLACK_BOT_TOKEN, SLACK_CHANNEL_ID
"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta

import feedparser
import requests

# ── 設定 ───────────────────────────────────────────
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "CA4N4ETA7")

RSS_FEEDS = [
    ("TechCrunch Japan", "https://jp.techcrunch.com/feed/"),
    ("ITmedia AI+",      "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml"),
    ("ASCII.jp",         "https://ascii.jp/rss.xml"),
    ("Gigazine",         "https://gigazine.net/news/rss_2.0/"),
    ("CNET Japan",       "https://japan.cnet.com/news/rss.htm"),
]

AI_KEYWORDS = [
    "AI", "人工知能", "機械学習", "ディープラーニング", "深層学習",
    "生成AI", "大規模言語モデル", "LLM", "GPT", "Claude", "Gemini",
    "ChatGPT", "Copilot", "自動化", "自律", "チャットボット",
    "画像生成", "音声認識", "自然言語", "データサイエンス",
    "OpenAI", "Anthropic", "Google DeepMind", "Meta AI", "Microsoft AI",
]

_TAG_RE = re.compile(r"<[^>]+>")
JST = timezone(timedelta(hours=9))


# ── ユーティリティ ──────────────────────────────────
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


def _is_ai_related(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in AI_KEYWORDS)


# ── Step 1: ニュース収集 ────────────────────────────
def collect_news(top_n: int = 10) -> list[dict]:
    all_items: list[dict] = []

    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                summary = _strip_html(getattr(entry, "summary", ""))[:300]
                if not _is_ai_related(entry.title, summary):
                    continue
                all_items.append({
                    "title":     entry.title,
                    "summary":   summary,
                    "url":       entry.link,
                    "published": _parse_date(entry),
                    "source":    source_name,
                })
        except Exception as exc:
            print(f"  [警告] {source_name} の取得に失敗: {exc}")

    all_items.sort(key=lambda x: x["published"], reverse=True)

    seen: set[str] = set()
    unique: list[dict] = []
    for item in all_items:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique[:top_n]


# ── Step 2: Slack メッセージ組み立て ────────────────
def build_message(news: list[dict]) -> str:
    now_jst = datetime.now(JST)
    date_str = now_jst.strftime("%Y年%m月%d日")
    time_str = now_jst.strftime("%Y-%m-%d %H:%M")

    lines = [
        f"📡 *最新 AI ニュース Top {len(news)}｜{date_str}*",
        "AIキーワードフィルタリング済みの最新情報をお届けします。",
        "",
    ]

    for i, item in enumerate(news, 1):
        lines.append(f"*{i}.* {item['title']}")
        lines.append(f"　[{item['source']}] {item['url']}")
        lines.append("")

    lines.append(f"_自動収集 by GitHub Actions　|　収集日時: {time_str} JST_")
    return "\n".join(lines)


# ── Step 3: Slack 投稿 ──────────────────────────────
def post_to_slack(message: str) -> None:
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "channel": SLACK_CHANNEL_ID,
            "text":    message,
            "mrkdwn":  True,
        },
        timeout=15,
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Slack API エラー: {result.get('error')}")
    print(f"  Slack 投稿完了: {result.get('ts')}")


# ── メイン ──────────────────────────────────────────
def main() -> None:
    print("=" * 55)
    print("  AI ニュース自動投稿 (GitHub Actions)")
    print("=" * 55)

    print("\n[1/3] AIニュースを収集中 ...")
    news = collect_news(top_n=10)
    if not news:
        print("ERROR: AI関連ニュースを1件も取得できませんでした。")
        sys.exit(1)
    print(f"  -> {len(news)} 件取得")
    for i, item in enumerate(news, 1):
        print(f"  {i:2}. [{item['source']}] {item['title'][:60]}")

    print("\n[2/3] Slack メッセージを作成中 ...")
    message = build_message(news)

    print("\n[3/3] Slack #general に投稿中 ...")
    post_to_slack(message)

    print("\n" + "=" * 55)
    print("  完了!")
    print("=" * 55)


if __name__ == "__main__":
    main()
