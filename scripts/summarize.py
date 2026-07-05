#!/usr/bin/env python3
"""AI Daily - 论文中文摘要提取

流程：读取 articles.json 中的论文 → 抓取 arXiv 英文正文 → 调 MiniMax 翻译 +
逐节提取中文摘要 → 保存为 docs/data/summaries/<id>.json（已存在则跳过）。
"""

import os
import re
import json
import time
import subprocess
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

MINIMAX_API_URL = os.environ.get(
    "MINIMAX_API_URL", "https://api.minimaxi.com/anthropic/v1/messages"
)
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7")
# 是否抓取 arXiv 真实全文。默认关闭：demo 数据的 arXiv 编号为占位，
# 抓真实全文会得到无关论文，导致摘要与标题不符，故基于标题生成。
USE_FULLTEXT = os.environ.get("USE_FULLTEXT", "0") == "1"
CST = timezone(timedelta(hours=8))

ROOT = Path(__file__).parent.parent
ARTICLES_FILE = ROOT / "docs" / "data" / "articles.json"
SUMMARY_DIR = ROOT / "docs" / "data" / "summaries"

UA = {"User-Agent": "Mozilla/5.0 (compatible; AIDailyBot/1.0)"}


def paper_id(url):
    """从 arXiv URL 提取论文 id，如 2607.01306"""
    m = re.search(r"(\d{4}\.\d{4,5})", url)
    if m:
        return m.group(1)
    return re.sub(r"[^A-Za-z0-9._-]", "_", url.rstrip("/").split("/")[-1])


def html_to_text(html):
    """把 arXiv HTML 转成带标题标记的纯文本"""
    html = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html)
    # 标题转成 ## 标记，方便模型识别章节
    html = re.sub(r"(?is)<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n\n## \1\n", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"&nbsp;", " ", html)
    html = re.sub(r"&amp;", "&", html)
    html = re.sub(r"&lt;", "<", html)
    html = re.sub(r"&gt;", ">", html)
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def fetch_paper_text(pid):
    """尝试抓取 arXiv 正文，成功返回文本，失败返回空串"""
    try:
        r = requests.get(f"https://arxiv.org/html/{pid}", timeout=20, headers=UA)
        if r.status_code == 200 and len(r.text) > 3000:
            text = html_to_text(r.text)
            if len(text) > 1500:
                return text[:9000]
    except Exception:
        pass
    return ""


def parse_minimax_content(result):
    """兼容 MiniMax extended thinking 的响应解析"""
    content = ""
    if "content" in result and isinstance(result["content"], list):
        for block in result["content"]:
            if isinstance(block, dict) and "text" in block:
                content = block["text"]
                break
            elif isinstance(block, str):
                content = block
                break
        if not content:
            for block in result["content"]:
                if isinstance(block, dict) and "thinking" in block:
                    content = block["thinking"]
                    break
    elif "choices" in result:
        content = result["choices"][0].get("message", {}).get("content", "")
    return content


def build_prompt(title, source, body):
    lines = [
        "你是AI论文翻译与解读专家。请对下面这篇论文生成结构化的中文摘要，供中文读者快速通读。",
        "",
        f"论文标题：{title}",
        f"来源：{source}",
        "",
    ]
    if body:
        lines += [
            "以下是论文正文（可能已截断），请基于它进行总结：",
            "-----",
            body,
            "-----",
        ]
    else:
        lines += [
            "（未能获取正文，请基于标题合理推断论文的典型章节结构与内容进行总结。）",
        ]
    lines += [
        "",
        "要求：",
        "1. titleCn：论文标题的中文翻译",
        "2. overview：100-160字的整体中文摘要，讲清研究问题、方法、结论",
        "3. sections：按论文主要章节逐节总结，5-6 节即可，每节 heading 用中文标题，summary 为该节 60-100 字中文总结；覆盖引言、方法、实验/结果、结论等",
        "",
        "只返回如下JSON，不要任何多余内容：",
        '{"titleCn":"...","overview":"...","sections":[{"heading":"...","summary":"..."}]}',
    ]
    return "\n".join(lines)


def summarize(title, source, body):
    prompt = build_prompt(title, source, body)
    last_err = None
    for attempt in range(3):
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
                    "max_tokens": 5000,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120,
            )
            response.raise_for_status()
            content = parse_minimax_content(response.json())
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if not m:
                raise ValueError("未匹配到JSON")
            return json.loads(m.group())
        except Exception as e:
            last_err = e
            print(f"   ↻ 第 {attempt + 1} 次失败: {e}")
            time.sleep(3)
    raise last_err


def git_push(path, msg):
    """每生成一篇立即提交，避免任务被超时取消时丢失进度"""
    if os.environ.get("PUSH_EACH") != "1":
        return
    try:
        subprocess.run(["git", "add", str(path)], check=True)
        subprocess.run(["git", "commit", "-m", msg], check=True)
        subprocess.run(["git", "push"], check=True)
    except Exception as e:
        print(f"   ⚠ push 失败: {e}")


def main():
    if not MINIMAX_API_KEY:
        print("✗ 未设置 MINIMAX_API_KEY")
        return

    data = json.load(open(ARTICLES_FILE, encoding="utf-8"))
    papers = [a for a in data["articles"] if a.get("category") == "论文"]
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    done = 0
    for a in papers:
        pid = paper_id(a["url"])
        out = SUMMARY_DIR / f"{pid}.json"
        if out.exists():
            continue

        print(f"📄 {pid} — {a['title'][:50]}")
        try:
            body = fetch_paper_text(pid) if USE_FULLTEXT else ""
            print(f"   正文 {len(body)} 字" if body else "   基于标题生成")
            result = summarize(a["title"], a["source"], body)
            result.update(
                {
                    "id": pid,
                    "title": a["title"],
                    "url": a["url"],
                    "source": a["source"],
                    "date": a.get("date", ""),
                    "hasFullText": bool(body),
                    "generatedAt": datetime.now(CST).isoformat(),
                }
            )
            json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            done += 1
            print(f"   ✓ 已保存 {len(result.get('sections', []))} 节")
            git_push(out, f"summary: {pid}")
        except Exception as e:
            print(f"   ✗ 失败: {e}")
        time.sleep(1)

    print(f"\n✅ 本次新增 {done} 篇摘要")


if __name__ == "__main__":
    main()
