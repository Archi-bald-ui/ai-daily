#!/usr/bin/env python3
"""AI Daily - 每日AI资讯抓取与评分"""

import os
import re
import json
import time
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# === 配置 ===
MINIMAX_API_URL = os.environ.get(
    "MINIMAX_API_URL", "https://api.minimaxi.com/anthropic/v1/messages"
)
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7")
SCORE_THRESHOLD = 6
MAX_PER_CATEGORY = 3
CST = timezone(timedelta(hours=8))
DATA_KEEP_DAYS = 30

# === 信源白名单 ===
SOURCES = [
    # 技术博客
    {
        "name": "OpenAI",
        "category": "技术博客",
        "feed_url": "https://openai.com/blog/rss.xml",
    },
    {
        "name": "Google AI",
        "category": "技术博客",
        "feed_url": "https://blog.google/technology/ai/rss/",
    },
    {
        "name": "HuggingFace",
        "category": "技术博客",
        "feed_url": "https://huggingface.co/blog/feed.xml",
    },
    {
        "name": "Anthropic",
        "category": "技术博客",
        "feed_url": "https://www.anthropic.com/research/rss.xml",
    },
    # 新闻资讯
    {
        "name": "The Verge AI",
        "category": "新闻资讯",
        "feed_url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    },
    {
        "name": "TechCrunch AI",
        "category": "新闻资讯",
        "feed_url": "https://techcrunch.com/category/artificial-intelligence/feed/",
    },
    {
        "name": "Ars Technica",
        "category": "新闻资讯",
        "feed_url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    },
    # 论文
    {
        "name": "arXiv cs.AI",
        "category": "论文",
        "feed_url": "https://rss.arxiv.org/rss/cs.AI",
    },
    {
        "name": "arXiv cs.CL",
        "category": "论文",
        "feed_url": "https://rss.arxiv.org/rss/cs.CL",
    },
    # 中文资讯
    {
        "name": "机器之心",
        "category": "中文资讯",
        "feed_url": "https://www.jiqizhixin.com/rss",
    },
    {
        "name": "量子位",
        "category": "中文资讯",
        "feed_url": "https://www.qbitai.com/feed",
    },
]


def fetch_feeds():
    """抓取所有 RSS 源，返回文章列表"""
    articles = []
    today = datetime.now(CST).date()

    for source in SOURCES:
        try:
            feed = feedparser.parse(source["feed_url"])
            count = 0
            for entry in feed.entries:
                if count >= 15:
                    break

                published = _parse_date(entry)
                if published:
                    article_date = published.astimezone(CST).date()
                    if (today - article_date).days > 2:
                        continue
                    date_str = article_date.isoformat()
                else:
                    date_str = today.isoformat()

                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                if not title or not url:
                    continue

                description = _clean_html(entry.get("summary", ""))[:200]

                articles.append(
                    {
                        "title": title,
                        "url": url,
                        "source": source["name"],
                        "category": source["category"],
                        "description": description,
                        "date": date_str,
                    }
                )
                count += 1

            print(f"  ✓ {source['name']}: {count} 篇")
        except Exception as e:
            print(f"  ✗ {source['name']}: {e}")

    return articles


def _parse_date(entry):
    """从 feed entry 中解析日期"""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _clean_html(text):
    """去除 HTML 标签"""
    return re.sub(r"<[^>]+>", "", text).strip()


def score_articles(articles):
    """用 MiniMax API 对文章打分"""
    if not articles or not MINIMAX_API_KEY:
        if not MINIMAX_API_KEY:
            print("  ⚠ 未设置 MINIMAX_API_KEY，跳过评分，所有文章默认 7 分")
            for a in articles:
                a["score"] = 7
        return articles

    scored = []

    for i in range(0, len(articles), 8):
        batch = articles[i : i + 8]
        prompt = _build_scoring_prompt(batch)

        try:
            response = requests.post(
                MINIMAX_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": MINIMAX_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": MINIMAX_MODEL,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()

            # 兼容 MiniMax extended thinking: content 数组中可能有 thinking 和 text 两种元素
            content = ""
            if "content" in result and isinstance(result["content"], list):
                for block in result["content"]:
                    if isinstance(block, dict) and "text" in block:
                        content = block["text"]
                        break
                    elif isinstance(block, str):
                        content = block
                        break
                # 如果只有 thinking 没有 text，从 thinking 中提取
                if not content:
                    for block in result["content"]:
                        if isinstance(block, dict) and "thinking" in block:
                            content = block["thinking"]
                            break
            elif "choices" in result:
                content = result["choices"][0].get("message", {}).get("content", "")

            print(f"  [DEBUG] 解析内容: {content[:200]}")

            json_match = re.search(r"\[.*\]", content, re.DOTALL)
            if json_match:
                scores = json.loads(json_match.group())
                for item in scores:
                    idx = item.get("index", 0) - 1
                    if 0 <= idx < len(batch):
                        batch[idx]["score"] = max(1, min(10, item.get("score", 5)))
                print(f"  ✓ 批次 {i // 8 + 1} 评分完成: {[a.get('score', '?') for a in batch]}")
            else:
                print(f"  ⚠ 批次 {i // 8 + 1} 未匹配到JSON数组")

            for a in batch:
                a.setdefault("score", 5)
            scored.extend(batch)

        except Exception as e:
            print(f"  ✗ 批次 {i // 8 + 1} 评分失败: {e}")
            for a in batch:
                a.setdefault("score", 5)
            scored.extend(batch)

        time.sleep(1)

    return scored


def _build_scoring_prompt(batch):
    """构建评分提示词"""
    lines = [
        "你是AI领域资讯编辑。请对以下文章逐一评估其对AI从业者的重要性和价值，给出1-10分。",
        "",
        "评分标准：",
        "- 9-10：重大突破、旗舰模型发布、行业格局变化",
        "- 7-8：值得关注的技术进展、重要产品更新、有影响力的研究",
        "- 5-6：一般性行业动态、常规更新",
        "- 1-4：旧闻、软文、无实质内容",
        "",
    ]
    for j, a in enumerate(batch):
        lines.append(f'{j + 1}. [{a["title"]}] — {a["source"]}')
        if a.get("description"):
            lines.append(f"   {a['description'][:120]}")
    lines.append("")
    lines.append('仅返回JSON数组，格式：[{"index": 1, "score": 8}, ...]')
    lines.append("不要输出任何其他内容。")
    return "\n".join(lines)


def filter_and_select(articles):
    """按阈值过滤 + 每类最多 3 篇"""
    qualified = [a for a in articles if a.get("score", 0) >= SCORE_THRESHOLD]

    by_category = {}
    for a in qualified:
        by_category.setdefault(a["category"], []).append(a)

    selected = []
    for cat, items in by_category.items():
        items.sort(key=lambda x: x.get("score", 0), reverse=True)
        selected.extend(items[:MAX_PER_CATEGORY])
        print(f"  {cat}: {min(len(items), MAX_PER_CATEGORY)}/{len(items)} 篇入选")

    return selected


def save_data(new_articles):
    """保存到 JSON，保留最近 30 天数据"""
    data_dir = Path(__file__).parent.parent / "docs" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    data_file = data_dir / "articles.json"

    existing = {"articles": [], "lastUpdated": ""}
    if data_file.exists():
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            pass

    existing_urls = {a["url"] for a in existing["articles"]}
    added = 0
    for a in new_articles:
        if a["url"] not in existing_urls:
            a.pop("description", None)
            existing["articles"].append(a)
            added += 1

    today = datetime.now(CST).date()
    existing["articles"] = [
        a
        for a in existing["articles"]
        if (today - datetime.strptime(a["date"], "%Y-%m-%d").date()).days
        <= DATA_KEEP_DAYS
    ]
    existing["articles"].sort(
        key=lambda x: (x["date"], x.get("score", 0)), reverse=True
    )
    existing["lastUpdated"] = datetime.now(CST).isoformat()

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"  新增 {added} 篇，总计 {len(existing['articles'])} 篇")


def main():
    print("=" * 50)
    print(f"AI Daily — {datetime.now(CST).strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    print("\n📡 抓取信源...")
    articles = fetch_feeds()
    print(f"共获取 {len(articles)} 篇文章")

    print("\n🤖 AI 评分...")
    scored = score_articles(articles)

    print("\n📊 筛选入围...")
    selected = filter_and_select(scored)
    print(f"最终入选 {len(selected)} 篇")

    print("\n💾 保存数据...")
    save_data(selected)

    print("\n✅ 完成！")


if __name__ == "__main__":
    main()
