"""
GitHub Actions 用スタンドアロン実行スクリプト
RSS収集 → AIフィルタリング / 量子コンピュータフィルタリング → Slack #general 投稿
環境変数: SLACK_BOT_TOKEN, SLACK_CHANNEL_ID
"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta

import feedparser
import requests

# ── 設定 ───────────────────────────────────────────
SLACK_BOT_TOKEN  = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "CA4N4ETA7")

RSS_FEEDS = [
    ("TechCrunch Japan", "https://jp.techcrunch.com/feed/"),
    ("ITmedia AI+",      "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml"),
    ("ASCII.jp",         "https://ascii.jp/rss.xml"),
    ("Gigazine",         "https://gigazine.net/news/rss_2.0/"),
    ("CNET Japan",       "https://japan.cnet.com/news/rss.htm"),
    ("ITmedia News",     "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"),
    ("日経 XTECH",        "https://xtech.nikkei.com/rss/index.rdf"),
]

AI_KEYWORDS = [
    "AI", "人工知能", "機械学習", "ディープラーニング", "深層学習",
    "生成AI", "大規模言語モデル", "LLM", "GPT", "Claude", "Gemini",
    "ChatGPT", "Copilot", "自動化", "自律", "チャットボット",
    "画像生成", "音声認識", "自然言語", "データサイエンス",
    "OpenAI", "Anthropic", "Google DeepMind", "Meta AI", "Microsoft AI",
]

QUANTUM_KEYWORDS = [
    "量子コンピュータ", "量子コンピューター", "量子計算", "量子ビット",
    "量子bit", "qubit", "量子優位", "量子超越", "量子暗号", "量子通信",
    "量子アルゴリズム", "量子エラー訂正", "量子もつれ", "量子ゲート",
    "量子回路", "量子プロセッサ", "量子チップ", "量子センサ",
    "IBM Quantum", "Google Quantum", "量子コンピューティング",
    "超伝導量子", "トポロジカル量子", "量子力学",
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


def _matches(title: str, summary: str, keywords: list[str]) -> bool:
    text = (title + " " + summary).lower()
    return any(kw.lower() in text for kw in keywords)


# ── ニュース収集（汎用） ────────────────────────────
def _fetch_all_entries() -> list[dict]:
    """全フィードからエントリを取得してキャッシュ"""
    all_entries = []
    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                summary = _strip_html(getattr(entry, "summary", ""))[:300]
                all_entries.append({
                    "title":     entry.title,
                    "summary":   summary,
                    "url":       entry.link,
                    "published": _parse_date(entry),
                    "source":    source_name,
                })
        except Exception as exc:
            print(f"  [警告] {source_name} の取得に失敗: {exc}")
    return all_entries


def _filter_and_rank(entries: list[dict], keywords: list[str], top_n: int) -> list[dict]:
    """キーワードでフィルタ → 新着順 → 重複排除 → 上位N件"""
    filtered = [
        e for e in entries
        if _matches(e["title"], e["summary"], keywords)
    ]
    filtered.sort(key=lambda x: x["published"], reverse=True)

    seen: set[str] = set()
    unique: list[dict] = []
    for item in filtered:
        key = item["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique[:top_n]


# ── Slack メッセージ組み立て ────────────────────────
def _build_message(news: list[dict], category: str, emoji: str, date_str: str, time_str: str) -> str:
    lines = [
        f"{emoji} *最新 {category} ニュース Top {len(news)}｜{date_str}*",
        f"キーワードフィルタリング済みの最新情報をお届けします。",
        "",
    ]
    for i, item in enumerate(news, 1):
        lines.append(f"*{i}.* {item['title']}")
        lines.append(f"　[{item['source']}] {item['url']}")
        lines.append("")
    lines.append(f"_自動収集 by GitHub Actions　|　収集日時: {time_str} JST_")
    return "\n".join(lines)


# ── Slack 投稿 ──────────────────────────────────────
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
    print("  AI・量子コンピュータ ニュース自動投稿 (GitHub Actions)")
    print("=" * 55)

    now_jst  = datetime.now(JST)
    date_str = now_jst.strftime("%Y年%m月%d日")
    time_str = now_jst.strftime("%Y-%m-%d %H:%M")

    # 全フィードを一括取得（重複リクエスト防止）
    print("\n[1/4] RSS フィードを取得中 ...")
    all_entries = _fetch_all_entries()
    print(f"  -> 総エントリ数: {len(all_entries)} 件")

    # AI ニュース
    print("\n[2/4] AI ニュースをフィルタリング中 ...")
    ai_news = _filter_and_rank(all_entries, AI_KEYWORDS, top_n=10)
    if not ai_news:
        print("  [警告] AI関連ニュースが0件でした")
    else:
        print(f"  -> {len(ai_news)} 件取得")
        for i, item in enumerate(ai_news, 1):
            print(f"  {i:2}. [{item['source']}] {item['title'][:55]}")

    # 量子コンピュータ ニュース
    print("\n[3/4] 量子コンピュータ ニュースをフィルタリング中 ...")
    quantum_news = _filter_and_rank(all_entries, QUANTUM_KEYWORDS, top_n=10)
    if not quantum_news:
        print("  [警告] 量子コンピュータ関連ニュースが0件でした")
    else:
        print(f"  -> {len(quantum_news)} 件取得")
        for i, item in enumerate(quantum_news, 1):
            print(f"  {i:2}. [{item['source']}] {item['title'][:55]}")

    if not ai_news and not quantum_news:
        print("ERROR: ニュースを1件も取得できませんでした。")
        sys.exit(1)

    # Slack 投稿（AI → 量子の順に2件投稿）
    print("\n[4/4] Slack #general に投稿中 ...")

    if ai_news:
        msg_ai = _build_message(ai_news, "AI", "📡", date_str, time_str)
        post_to_slack(msg_ai)

    if quantum_news:
        msg_quantum = _build_message(quantum_news, "量子コンピュータ", "⚛️", date_str, time_str)
        post_to_slack(msg_quantum)

    print("\n" + "=" * 55)
    print("  完了!")
    print("=" * 55)


if __name__ == "__main__":
    main()
