#!/usr/bin/env python3
"""
AI ニュース収集ワークフロー ― 一括実行スクリプト

使い方:
    python run_all.py

完了後、Claude Code に「Slack に投稿して」と伝えると
#general チャンネルへ自動投稿されます。
"""
import json
import os
import sys
from datetime import datetime


def main() -> None:
    print("=" * 62)
    print("  AI ニュース自動収集ワークフロー")
    print("=" * 62)

    # ── Step 1: ニュース収集 ────────────────────────────
    print("\n[1/3] AI ニュースを収集中 ...")
    from collect_news import collect_news
    news = collect_news(top_n=10)
    if not news:
        print("ERROR: ニュースを1件も取得できませんでした。")
        print("      インターネット接続または RSS フィードを確認してください。")
        sys.exit(1)
    print(f"  -> {len(news)} 件取得")
    for i, item in enumerate(news, 1):
        print(f"  {i:2}. [{item['source']}] {item['title'][:60]}")

    # ── Step 2: Excel 保存 ──────────────────────────────
    print("\n[2/3] Excel に保存中 ...")
    from save_to_excel import save_to_excel
    excel_path = save_to_excel(news)

    # ── Step 3: PowerPoint 生成 ─────────────────────────
    print("\n[3/3] PowerPoint を生成中 ...")
    from create_pptx import create_pptx
    pptx_path = create_pptx(news)

    # ── サマリー JSON を書き出す（Claude Code が Slack 投稿に使う）──
    summary = {
        "collected_at": datetime.now().isoformat(),
        "count":        len(news),
        "excel_path":   excel_path,
        "pptx_path":    pptx_path,
        "news": [
            {"no": i + 1, "title": n["title"], "source": n["source"], "url": n["url"]}
            for i, n in enumerate(news)
        ],
    }
    summary_path = os.path.join(os.path.dirname(__file__), "output", "last_run_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ── 完了メッセージ ──────────────────────────────────
    print("\n" + "=" * 62)
    print("  完了!")
    print(f"  Excel       : {excel_path}")
    print(f"  PowerPoint  : {pptx_path}")
    print(f"  サマリー JSON: {summary_path}")
    print("=" * 62)
    print()
    print("次のステップ:")
    print("  Claude Code に「Slack に投稿して」と伝えてください。")
    print("  #general チャンネルへニュースサマリーが投稿されます。")


if __name__ == "__main__":
    main()
